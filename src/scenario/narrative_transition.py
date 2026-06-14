"""v1.8 M0 — L3 narrative transition gate.

Anchors (timeline events with ``anchor: true``) are the deterministic backbone:
the script defines the 大走向, the LLM only fills the gaps BETWEEN anchors. A
generated *beat* carries render-only prose (-> ``Event.narration`` only) plus AT
MOST one bounded, whitelisted mechanical command.

The safety core is **write-set non-interference**: a beat's write set must not
intersect the read set of ANY pending anchor precondition. Combined with the
narrow Q2 whitelist (initially only a bounded relation delta), this guarantees a
beat can never starve a scheduled anchor — the L3 promise that 锚点必触发、走向被夹住.

Why NOT ``apply_effects``: it skips rollback snapshots for non-picklable live
objects and dispatches arbitrary registered mod-effect callables, so it cannot
enforce an authority boundary. Beats go through the dedicated, whitelist-only
applier below instead. The generator receives an immutable snapshot, never the
live ``world``.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any

from src.classes.event import Event

from .state_access import as_id, get_relation, get_relations, set_relation

LOGGER = logging.getLogger(__name__)

# Q2 (locked): the ONLY stateful command L3 may apply initially. Flags, vars,
# storyline activation, world-event triggers, entity death/realm/membership, and
# registered mod effects are all excluded — they feed anchor preconditions or are
# unbounded. The whitelist grows only in lockstep with `command_write_set` below.
TRANSITION_COMMAND_WHITELIST = {"relation_delta"}

RELATION_DELTA_MAX = 10  # bounded magnitude per beat (Q2: "the delta is bounded")

# strict tick-level bound (Q4), well under the 120s provider timeout; mirrors v1.7
TRANSITION_TIMEOUT_SECONDS = 30.0
TRANSITION_BUDGET = 4  # max beats requested/considered per gap tick (Q4 budget)


# --- read-set / write-set extraction (the invariant rests on these) ----------


def condition_read_set(expression: Any) -> set[tuple]:
    """The set of mechanical facts a condition DSL expression READS.

    Returned tokens: ``("relation", frozenset({a, b}))``, ``("flag", name)``,
    ``("var", name)``, ``("event", id)``. Player-relations use the ``"@player"``
    sentinel as one endpoint. Predicates that the whitelist can never write are
    intentionally not extracted — this MUST stay in lockstep with the whitelist:
    every command-writable namespace has to be represented here.
    """
    if not isinstance(expression, dict) or len(expression) != 1:
        return set()
    key, value = next(iter(expression.items()))
    if key in ("all", "any"):
        reads: set[tuple] = set()
        for item in value or []:
            reads |= condition_read_set(item)
        return reads
    if key == "not":
        return condition_read_set(value)

    params = value or {}
    if not isinstance(params, dict):
        return set()
    if key == "world_flag":
        return {("flag", str(params.get("flag")))}
    if key == "var_equals":
        return {("var", str(params.get("name")))}
    if key == "event_triggered":
        return {("event", as_id(params.get("event_id")))}
    if key == "npc_relation":
        return {("relation", frozenset({as_id(params.get("a")), as_id(params.get("b"))}))}
    if key == "player_relation":
        return {("relation", frozenset({"@player", as_id(params.get("npc_id"))}))}
    return set()


def command_write_set(command: dict[str, Any]) -> set[tuple]:
    """The set of mechanical facts a whitelisted transition command WRITES."""
    name = str(command.get("command", ""))
    if name == "relation_delta":
        return {("relation", frozenset({as_id(command.get("a")), as_id(command.get("b"))}))}
    return set()


def pending_anchor_read_set(timeline: list[dict[str, Any]], triggered: set[str]) -> set[tuple]:
    """Union of read sets of every anchor that has NOT yet fired — the facts a
    transition beat must leave untouched, or it could starve a future anchor."""
    reads: set[tuple] = set()
    for event in timeline:
        if not event.get("anchor"):
            continue
        if str(event.get("id", "")) in triggered:
            continue
        reads |= condition_read_set((event.get("trigger", {}) or {}).get("condition"))
    return reads


# --- validation + deterministic application ----------------------------------


def validate_beat(beat: dict[str, Any], protected: set[tuple]) -> tuple[bool, str | None]:
    """Returns (accepted, rejection_reason). A beat with no command is pure
    narration (always accepted, zero mechanical effect)."""
    command = beat.get("command")
    if command is None:
        return True, None
    if not isinstance(command, dict):
        return False, "command must be an object"
    name = str(command.get("command", ""))
    if name not in TRANSITION_COMMAND_WHITELIST:
        return False, f"command not whitelisted: {name}"
    if name == "relation_delta":
        try:
            delta = int(command.get("delta", 0))
        except (TypeError, ValueError):
            return False, "relation delta must be an integer"
        if abs(delta) > RELATION_DELTA_MAX:
            return False, f"relation delta {delta} exceeds bound {RELATION_DELTA_MAX}"
    if command_write_set(command) & protected:
        return False, "write-set intersects a pending anchor precondition"
    return True, None


def apply_beat_command(state: Any, command: dict[str, Any]) -> None:
    """Deterministically apply a single VALIDATED whitelisted command. Never call
    with an unvalidated command — validation is the authority boundary."""
    name = str(command.get("command", ""))
    if name == "relation_delta":
        a, b = command.get("a"), command.get("b")
        set_relation(state, a, b, get_relation(state, a, b) + int(command.get("delta", 0)))


# --- gap detection + snapshot + the phase entry point -------------------------


def _is_gap_tick(timeline: list[dict[str, Any]], triggered: set[str], fired_ids: set[str]) -> bool:
    """A gap tick is BETWEEN anchors: at least one anchor already fired, at least
    one anchor is still pending, and no anchor fired this very month."""
    anchors = [e for e in timeline if e.get("anchor")]
    if not anchors:
        return False
    anchor_ids = {str(e.get("id", "")) for e in anchors}
    if anchor_ids & fired_ids:
        return False  # an anchor fired this month — this is an anchor tick, not a gap
    past = any(aid in triggered for aid in anchor_ids)
    pending = any(aid not in triggered for aid in anchor_ids)
    return past and pending


def _build_snapshot(world: Any, state: Any, pending_ids: list[str]) -> dict[str, Any]:
    """An IMMUTABLE-by-convention read view for the generator. Deliberately not
    the live ``world`` — the generator returns data only, never mutates."""
    return {
        "year": int(getattr(getattr(world, "month_stamp", None), "get_year", lambda: 0)()),
        "month": int(getattr(getattr(world, "month_stamp", None), "get_month", lambda: 0)().value)
        if getattr(world, "month_stamp", None) is not None
        else 0,
        "relations": dict(get_relations(state)),
        "pending_anchor_ids": list(pending_ids),
    }


def _beat_event(world: Any, beat: dict[str, Any]) -> Event:
    # prose lives ONLY on the render-only narration channel; content stays empty so
    # the beat never enters AI memory / chronicle (is_story=True keeps it out of the
    # memory index too).
    return Event(
        month_stamp=world.month_stamp,
        content="",
        narration=str(beat.get("narration") or ""),
        is_story=True,
        event_type="scenario",
        render_key="scenario.transition",
        render_params={"transition_beat_id": str(beat.get("id") or "")},
        id=str(beat.get("id") or ""),
    )


async def apply_narrative_transition(
    world: Any, state: Any, fired_ids: set[str]
) -> list[Event]:
    """Generate, validate, and apply L3 transition beats for a gap tick.

    Runs AFTER anchors have already dispatched this month, so anchors always take
    priority. No generator / failure / timeout → returns ``[]`` (anchors already
    fired; the game stays playable). Accepted beats apply their bounded command
    through ``apply_beat_command`` and emit render-only narration events; every
    decision (accept/reject + reason) is recorded on the non-``state`` ledger.
    """
    generator = getattr(world, "transition_generator", None)
    if generator is None:
        return []
    sc = getattr(world, "scripted_scenario", None)
    if sc is None:
        return []

    triggered = set(str(t) for t in getattr(sc, "triggered_events", set()) or set())
    if not _is_gap_tick(sc.timeline, triggered, fired_ids):
        return []

    protected = pending_anchor_read_set(sc.timeline, triggered)
    pending_ids = [
        str(e.get("id", ""))
        for e in sc.timeline
        if e.get("anchor") and str(e.get("id", "")) not in triggered
    ]
    snapshot = _build_snapshot(world, state, pending_ids)

    budget = int(getattr(world, "transition_budget", TRANSITION_BUDGET))
    timeout = float(getattr(world, "transition_timeout", TRANSITION_TIMEOUT_SECONDS))
    try:
        proposals = generator(snapshot)
        if inspect.isawaitable(proposals):
            proposals = await asyncio.wait_for(proposals, timeout)
    except Exception:  # noqa: BLE001 — a generator failure/timeout must never break the tick
        LOGGER.warning("transition_generator failed/timed out; skipping gap beats", exc_info=True)
        return []
    if not isinstance(proposals, list):
        return []

    ledger = getattr(sc, "transition_ledger", None)
    if not isinstance(ledger, list):
        ledger = []
    month_stamp = str(int(world.month_stamp)) if getattr(world, "month_stamp", None) is not None else ""

    events: list[Event] = []
    for beat in proposals[:budget]:
        if not isinstance(beat, dict):
            continue
        beat_id = str(beat.get("id") or "")
        accepted, reason = validate_beat(beat, protected)
        record = {"month_stamp": month_stamp, "beat_id": beat_id, "accepted": accepted}
        if not accepted:
            record["reason"] = reason
            ledger.append(record)
            continue
        command = beat.get("command")
        if isinstance(command, dict):
            apply_beat_command(state, command)
            record["command"] = dict(command)
        ledger.append(record)
        events.append(_beat_event(world, beat))

    # persist relation writes back to the scenario state (the dispatch view is a
    # shallow copy whose `relations` key may not be the same object) and the ledger
    sc.state["relations"] = dict(get_relations(state))
    sc.transition_ledger = ledger
    return events
