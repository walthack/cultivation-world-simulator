from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any

from src.classes.event import Event
from src.classes.language import language_manager
from src.scenario.event_dispatcher import EventDispatcher
from src.scenario.narration_cache import narration_cache_key, resolved_outcome
from src.scenario.event_handlers import (
    handle_branch,
    handle_character_introduction,
    handle_ending,
    handle_main_event,
    handle_relation_change,
    handle_side_event,
    handle_world_event,
)


_HANDLERS = {
    "main": handle_main_event,
    "side_event": handle_side_event,
    "sect_event": handle_side_event,
    "world_event": handle_world_event,
    "branch": handle_branch,
    "character_introduction": handle_character_introduction,
    "relation_change": handle_relation_change,
    "relationship_event": handle_relation_change,
    "ending": handle_ending,
}


def _scenario_player(world: Any, scenario_state: dict[str, Any]) -> Any:
    controlled_avatar = scenario_state.get("controlled_avatar")
    npcs = scenario_state.get("npcs")
    if controlled_avatar and isinstance(npcs, dict):
        npc = npcs.get(str(controlled_avatar))
        if npc is not None:
            return npc
    if controlled_avatar:
        avatar = world.avatar_manager.get_avatar(str(controlled_avatar))
        if avatar is not None:
            return avatar

    for avatar in world.avatar_manager.avatars.values():
        return avatar

    if isinstance(npcs, dict):
        for npc in npcs.values():
            return npc
    return {}


def _build_dispatch_state(world: Any, sc: Any) -> dict[str, Any]:
    scenario_state = sc.state
    world_flags = scenario_state.setdefault("world_flags", {})
    if isinstance(world_flags, dict):
        world.world_flags.update(world_flags)

    runtime = {
        "scenario_id": sc.scenario_id,
        "triggered_event_ids": sorted(sc.triggered_events),
        "blocked_event_ids": list(scenario_state.get("blocked_event_ids", []) or []),
        "event_outcomes": dict(scenario_state.get("event_outcomes", {}) or {}),
        "dispatch_log": list(getattr(sc, "dispatch_log", []) or []),
    }
    state = {
        **scenario_state,
        "player": _scenario_player(world, scenario_state),
        "world": world,
        "roleplay_session": getattr(getattr(world, "runtime", None), "get_roleplay_session", lambda: {})(),
        "scenario_runtime": runtime,
        "scripted_scenario_state": scenario_state,
    }
    return state


def _sync_dispatch_state(sc: Any, dispatch_state: dict[str, Any]) -> None:
    runtime = dispatch_state.get("scenario_runtime", {}) or {}
    sc.triggered_events = set(str(item) for item in runtime.get("triggered_event_ids", []) or [])
    sc.state["blocked_event_ids"] = list(runtime.get("blocked_event_ids", []) or [])
    sc.state["event_outcomes"] = dict(runtime.get("event_outcomes", {}) or {})
    sc.dispatch_log = list(runtime.get("dispatch_log", []) or [])[-50:]


def _to_event(world: Any, scenario_event: dict[str, Any]) -> Event:
    event_id = str(scenario_event.get("id") or "")
    return Event(
        month_stamp=world.month_stamp,
        content=str(scenario_event.get("description") or scenario_event.get("name") or event_id),
        is_major=str(scenario_event.get("type") or "") == "main",
        event_type="scenario",
        render_key="scenario.event",
        render_params={
            "scenario_event_id": event_id,
            "scenario_event_name": str(scenario_event.get("name") or ""),
        },
        id=event_id,
    )


async def phase_scripted_scenario_tick(world: Any, ctx: Any) -> list[Event]:
    sc = getattr(world, "scripted_scenario", None)
    if sc is None:
        return []

    dispatch_state = _build_dispatch_state(world, sc)
    dispatcher = EventDispatcher(sc.timeline, handlers=_HANDLERS)
    month_stamp = ctx.month_stamp or world.month_stamp
    dispatched = await dispatcher.dispatch_month(
        dispatch_state,
        year=int(month_stamp.get_year()),
        month=int(month_stamp.get_month().value),
    )
    _sync_dispatch_state(sc, dispatch_state)
    events = [_to_event(world, scenario_event) for scenario_event in dispatched]
    await _apply_narrative_fill(world, events, dispatched)
    return events


NARRATIVE_FILL_TIMEOUT_SECONDS = 30.0  # strict tick-level bound, well under the 120s provider timeout (Q1b)
NARRATIVE_FILL_BUDGET = 8  # max generated narrations per tick (Q11)


async def _apply_narrative_fill(world: Any, events: list[Event], scenario_events: list[dict[str, Any]]) -> None:
    """v1.7 render-only fill. Writes ONLY event.narration — never touches content,
    world state, effects, flags, or branch outcome. Opt-in via `narrative_fill: true`.

    Q1b: ONE bounded batch call to the injectable `world.narrative_filler`
    (`(requests, world) -> {event_id: narration}`) per tick, wrapped in a single
    tick-level timeout (the whole batch is bounded regardless of event count). Q11
    budget caps how many events the filler is asked to generate. narration = the
    returned text when non-empty, else the authored `narration_fallback` (Q2/Q9).
    No filler / failure / timeout → fallback; no-LLM environments stay playable.

    M2 (Q3/Q9): generated narration is reproducible. Each fillable event is keyed
    by (scenario_id, event_id, resolved_outcome, content_locale) against the
    save-persisted `narration_cache`. A cache HIT reuses the frozen text and
    consumes no LLM call/budget. A MISS generates once and freezes the result.
    Generation failure → authored fallback, which is NOT cached: it is static and
    thus already reproducible, and leaving it uncached lets a later LLM-available
    run fill it in (the permanent-fallback recovery never forces non-reproducible
    regeneration of an already-frozen entry)."""
    fillable = [(ev, se) for ev, se in zip(events, scenario_events) if se.get("narrative_fill")]
    if not fillable:
        return

    sc = getattr(world, "scripted_scenario", None)
    cache = getattr(sc, "narration_cache", None)
    if not isinstance(cache, dict):
        cache = {}
    scenario_id = getattr(sc, "scenario_id", "")
    locale = getattr(language_manager, "current", "")
    event_outcomes = (getattr(sc, "state", {}) or {}).get("event_outcomes", {}) or {}

    keys: dict[str, str] = {}
    to_generate: list[tuple[Event, dict[str, Any]]] = []
    for event, scenario_event in fillable:
        event_id = str(scenario_event.get("id"))
        key = narration_cache_key(
            scenario_id, event_id, resolved_outcome(event_id, event_outcomes), locale
        )
        keys[event_id] = key
        cached = cache.get(key)
        if isinstance(cached, str) and cached.strip():
            event.narration = cached  # frozen text — no LLM call, no budget
        else:
            to_generate.append((event, scenario_event))

    generated: dict[str, Any] = {}
    if to_generate:
        budget = int(getattr(world, "narrative_fill_budget", NARRATIVE_FILL_BUDGET))
        timeout = float(getattr(world, "narrative_fill_timeout", NARRATIVE_FILL_TIMEOUT_SECONDS))
        filler = getattr(world, "narrative_filler", None)
        requests = [se for _, se in to_generate]
        if filler is not None:
            try:
                result = filler(requests[:budget], world)
                if inspect.isawaitable(result):
                    result = await asyncio.wait_for(result, timeout)
                if isinstance(result, dict):
                    generated = result
            except Exception:  # noqa: BLE001 — a filler failure/timeout must never break the tick
                logging.getLogger(__name__).warning(
                    "narrative_filler batch failed/timed out (%d events); using authored fallback",
                    len(requests),
                    exc_info=True,
                )
                generated = {}

    for event, scenario_event in to_generate:
        event_id = str(scenario_event.get("id"))
        text = generated.get(event_id)
        if isinstance(text, str) and text.strip():
            event.narration = text
            cache[keys[event_id]] = text  # freeze generated text for reproducibility
        else:
            event.narration = scenario_event.get("narration_fallback")  # static, not cached

    if sc is not None and cache:
        sc.narration_cache = cache
