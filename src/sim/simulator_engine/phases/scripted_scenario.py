from __future__ import annotations

import logging
from typing import Any

from src.classes.event import Event
from src.scenario.event_dispatcher import EventDispatcher
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
    return [_fill_narration(world, _to_event(world, scenario_event), scenario_event) for scenario_event in dispatched]


def _fill_narration(world: Any, event: Event, scenario_event: dict[str, Any]) -> Event:
    """v1.7 render-only fill. Writes ONLY event.narration — never touches content,
    world state, effects, flags, or branch outcome. Opt-in via the scenario event's
    `narrative_fill: true`. narration = LLM text when an injectable
    `world.narrative_filler` yields a non-empty string, else the authored
    `narration_fallback` (Q2/Q9 — permanent fallback on no-filler / failure / miss;
    no-LLM environments stay playable). Default (no filler) → fallback."""
    if not scenario_event.get("narrative_fill"):
        return event
    fallback = scenario_event.get("narration_fallback")
    text: Any = None
    filler = getattr(world, "narrative_filler", None)
    if filler is not None:
        try:
            text = filler(scenario_event, world)
        except Exception:  # noqa: BLE001 — a filler failure must never break the tick
            logging.getLogger(__name__).warning(
                "narrative_filler failed for event %s; using authored fallback",
                scenario_event.get("id"),
                exc_info=True,
            )
            text = None
    event.narration = text if isinstance(text, str) and text.strip() else fallback
    return event
