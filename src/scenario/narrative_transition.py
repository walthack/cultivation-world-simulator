"""v1.8 M0 — L3 narrative transition gate.

Anchors (timeline events with ``anchor: true``) are the deterministic backbone:
the script defines the 大走向, the LLM only fills the gaps BETWEEN anchors. A
generated *beat* carries render-only prose (-> ``Event.narration`` only) plus AT
MOST one bounded, whitelisted mechanical command.

The safety core is **write-set non-interference**: a beat's write set must not
intersect the read set of ANY pending anchor precondition. Combined with the
narrow Q2 whitelist (initially only a bounded relation delta), this guarantees a
beat can never starve a scheduled anchor — the L3 promise that 锚点必触发、走向被夹住.

Read-set extraction is **fail-closed**: a condition predicate we cannot model
precisely (a registered mod predicate, or a ``var_equals`` that reads a structural
state sub-object such as ``relations``) yields the ``PROTECT_ALL`` sentinel, which
intersects every non-empty write set and so rejects every stateful beat. Silent
under-extraction would be a starvation hole, so we err toward rejection.

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

from .state_access import as_id, get_player, get_relation, get_relations, get_value, set_relation

LOGGER = logging.getLogger(__name__)

# Q2 (locked): the ONLY stateful command L3 may apply initially. Flags, vars,
# storyline activation, world-event triggers, entity death/realm/membership, and
# registered mod effects are all excluded — they feed anchor preconditions or are
# unbounded. The whitelist grows only in lockstep with `command_write_set` AND a
# re-audit of `condition_read_set` (every command-writable namespace must be
# extractable there, or fail closed).
TRANSITION_COMMAND_WHITELIST = {"relation_delta"}

RELATION_DELTA_MAX = 10  # bounded magnitude per beat (Q2: "the delta is bounded")

# sentinel: a read set we cannot model precisely; intersects every write set.
PROTECT_ALL: tuple = ("*", "*")

# var_equals reads the WHOLE scenario state (get_scenario_vars returns sc.state),
# so a var_equals over a structural sub-object that a command can mutate is a
# write-set collision we must treat as universal. `relations` is the only one a
# relation_delta touches; the rest are listed for when the whitelist grows.
_STRUCTURAL_STATE_KEYS = {"relations", "world_flags", "active_storylines"}

# atomic predicates we model precisely AND that no current whitelisted command can
# affect — safe to extract as an empty read set. Anything NOT here and not handled
# explicitly below is treated as unknown → PROTECT_ALL.
_RELATION_INERT_PREDICATES = {
    "always",
    "controlled_avatar_is",
    "player_realm",
    "player_sect",
    "player_has_skill",
    "player_stat",
    "world_year",
    "world_month",
    "npc_alive",
    "npc_realm",
    "random_chance",
}
# the player-endpoint sentinel inside a statically-extracted relation token; the
# real player id is substituted in `pending_anchor_read_set`.
PLAYER_SENTINEL = "@player"


# --- read-set / write-set extraction (the invariant rests on these) ----------


def condition_read_set(expression: Any) -> set[tuple]:
    """The set of mechanical facts a condition DSL expression READS (fail-closed).

    Tokens: ``("relation", frozenset({a, b}))``, ``("flag", name)``,
    ``("var", name)``, ``("event", id)``, or ``PROTECT_ALL`` for anything we can't
    model. Player-relations use ``PLAYER_SENTINEL`` as one endpoint.
    """
    if not isinstance(expression, dict) or len(expression) != 1:
        return {PROTECT_ALL}  # malformed → fail closed
    key, value = next(iter(expression.items()))
    if key in ("all", "any"):
        reads: set[tuple] = set()
        for item in value or []:
            reads |= condition_read_set(item)
        return reads
    if key == "not":
        return condition_read_set(value)

    params = value if isinstance(value, dict) else {}
    if key == "world_flag":
        return {("flag", str(params.get("flag")))}
    if key == "event_triggered":
        return {("event", as_id(params.get("event_id")))}
    if key == "npc_relation":
        return {("relation", frozenset({as_id(params.get("a")), as_id(params.get("b"))}))}
    if key == "player_relation":
        return {("relation", frozenset({PLAYER_SENTINEL, as_id(params.get("npc_id"))}))}
    if key == "var_equals":
        name = str(params.get("name"))
        if name in _STRUCTURAL_STATE_KEYS:
            return {PROTECT_ALL}  # reads a structural sub-object a command can mutate
        return {("var", name)}
    if key in _RELATION_INERT_PREDICATES:
        return set()
    return {PROTECT_ALL}  # unknown / mod predicate → fail closed


def command_write_set(command: dict[str, Any]) -> set[tuple]:
    """The set of mechanical facts a whitelisted transition command WRITES."""
    name = str(command.get("command", ""))
    if name == "relation_delta":
        return {("relation", frozenset({as_id(command.get("a")), as_id(command.get("b"))}))}
    return set()


def pending_anchor_read_set(
    timeline: list[dict[str, Any]],
    triggered: set[str],
    *,
    player_id: Any,
    now: tuple[int, int],
) -> set[tuple]:
    """Union of read sets over the PRECONDITION CLOSURE of every future-or-current
    pending anchor — the facts a transition beat must leave untouched, or it could
    starve an anchor.

    Protecting only an anchor's own condition is NOT enough (codex M1 review): an
    anchor's reachability also depends on the conditions of every event it
    transitively requires and of the activators of any storyline that gates it. A
    beat that breaks a *required* event's condition starves the anchor even when
    the anchor's own condition is ``always``. So the protected set is the closure.

    Past-due unfired anchors are excluded (already missed, not protectable). The
    ``PLAYER_SENTINEL`` endpoint is resolved to the real player id so a beat acting
    on ``(player_id, npc)`` cannot bypass a ``player_relation`` precondition.
    """
    resolved = as_id(player_id)
    reads: set[tuple] = set()
    for event in timeline:
        if not event.get("anchor"):
            continue
        if str(event.get("id", "")) in triggered:
            continue
        if _anchor_when(event) < now:
            continue  # past-due missed anchor — not a future obligation
        for node in _precondition_closure(timeline, event):
            for token in condition_read_set((node.get("trigger", {}) or {}).get("condition")):
                if token[0] == "relation" and PLAYER_SENTINEL in token[1]:
                    token = ("relation", frozenset({resolved if e == PLAYER_SENTINEL else e for e in token[1]}))
                reads.add(token)
    return reads


def _activate_storyline_targets(event: dict[str, Any]) -> set[str]:
    """Storyline ids an event can activate (top-level / choice / branch effects)."""
    targets: set[str] = set()

    def scan(effects: Any) -> None:
        for effect in effects or []:
            if isinstance(effect, dict) and effect.get("type") == "activate_storyline":
                sl = effect.get("storyline")
                if sl:
                    targets.add(str(sl))

    scan(event.get("effects"))
    for choice in event.get("choices") or []:
        if isinstance(choice, dict):
            scan(choice.get("effects"))
    for branch in event.get("branches") or []:
        if isinstance(branch, dict):
            scan(branch.get("effects"))
    return targets


def _precondition_closure(timeline: list[dict[str, Any]], anchor: dict[str, Any]) -> list[dict[str, Any]]:
    """Transitive closure of nodes whose conditions gate an anchor: the anchor, its
    transitive ``requires_events``, and the activators of any storyline tag found
    along the way. Conditions of all these nodes must be protected from beats."""
    by_id = {str(e.get("id", "")): e for e in timeline}
    activators: dict[str, list[dict[str, Any]]] = {}
    for event in timeline:
        for sl in _activate_storyline_targets(event):
            activators.setdefault(sl, []).append(event)

    seen: set[str] = set()
    stack: list[dict[str, Any]] = [anchor]
    nodes: list[dict[str, Any]] = []
    while stack:
        node = stack.pop()
        nid = str(node.get("id", ""))
        if nid in seen:
            continue
        seen.add(nid)
        nodes.append(node)
        for required in node.get("requires_events", []) or []:
            dep = by_id.get(str(required))
            if dep is not None:
                stack.append(dep)
        storyline = node.get("storyline")
        if storyline is not None:
            stack.extend(activators.get(str(storyline), []))
    return nodes


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
        a_id, b_id = as_id(command.get("a")), as_id(command.get("b"))
        if not a_id or not b_id:
            return False, "relation_delta requires non-empty a and b"
        if a_id == b_id:
            return False, "relation_delta endpoints must differ"
        delta = command.get("delta")
        if not isinstance(delta, int) or isinstance(delta, bool):
            return False, "relation delta must be an integer"
        if delta == 0:
            return False, "relation delta must be nonzero"
        if abs(delta) > RELATION_DELTA_MAX:
            return False, f"relation delta {delta} exceeds bound {RELATION_DELTA_MAX}"
    write = command_write_set(command)
    if write and (PROTECT_ALL in protected or write & protected):
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


def _anchor_when(event: dict[str, Any]) -> tuple[int, int]:
    trigger = event.get("trigger", {}) or {}
    return int(trigger.get("year", -1)), int(trigger.get("month", -1))


def _is_gap_tick(
    timeline: list[dict[str, Any]], triggered: set[str], fired_ids: set[str], now: tuple[int, int]
) -> bool:
    """A gap tick is BETWEEN anchors: at least one anchor already fired, at least
    one FUTURE anchor is still pending, and no anchor fired this very month.
    Past-due unfired anchors do NOT keep the gap open (else generation runs
    forever after a missed anchor)."""
    anchors = [e for e in timeline if e.get("anchor")]
    if not anchors:
        return False
    anchor_ids = {str(e.get("id", "")) for e in anchors}
    if anchor_ids & fired_ids:
        return False  # an anchor fired this month — this is an anchor tick, not a gap
    past = any(aid in triggered for aid in anchor_ids)
    future_pending = any(
        str(e.get("id", "")) not in triggered and _anchor_when(e) >= now for e in anchors
    )
    return past and future_pending


def _now(world: Any) -> tuple[int, int]:
    stamp = getattr(world, "month_stamp", None)
    if stamp is None:
        return (0, 0)
    return int(stamp.get_year()), int(stamp.get_month().value)


def _build_snapshot(world: Any, state: Any, pending_ids: list[str], now: tuple[int, int]) -> dict[str, Any]:
    """An IMMUTABLE-by-convention read view for the generator. Deliberately NOT the
    live ``world`` — the generator returns data only, never mutates. (The interface
    cannot prevent a hostile closure from capturing ``world``; this is by
    convention, like every injectable in the engine.)"""
    return {
        "year": now[0],
        "month": now[1],
        "relations": dict(get_relations(state)),
        "pending_anchor_ids": list(pending_ids),
    }


def _beat_event(world: Any, beat: dict[str, Any]) -> Event:
    # prose lives ONLY on the render-only narration channel; content stays empty so
    # the beat never enters AI memory / chronicle (is_story=True keeps it out of the
    # memory index, and _chronicle_context filters is_story too).
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


async def apply_narrative_transition(world: Any, state: Any, fired_ids: set[str]) -> list[Event]:
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
    now = _now(world)
    if not _is_gap_tick(sc.timeline, triggered, fired_ids, now):
        return []

    # M2 cadence (Q4): throttle generation within a long gap — ask the generator at
    # most once per `transition_cadence_months`. Default 1 = every gap month.
    cadence = max(1, int(getattr(world, "transition_cadence_months", 1)))
    total_now = now[0] * 12 + now[1]
    if total_now - int(getattr(sc, "transition_last_gen_month", -10**9)) < cadence:
        return []
    sc.transition_last_gen_month = total_now

    player_id = get_value(get_player(state), "id")
    protected = pending_anchor_read_set(sc.timeline, triggered, player_id=player_id, now=now)
    pending_ids = [
        str(e.get("id", ""))
        for e in sc.timeline
        if e.get("anchor") and str(e.get("id", "")) not in triggered and _anchor_when(e) >= now
    ]
    snapshot = _build_snapshot(world, state, pending_ids, now)

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


# strict tick-level bound (Q4), well under the 120s provider timeout; mirrors v1.7
TRANSITION_TIMEOUT_SECONDS = 30.0
TRANSITION_BUDGET = 4  # max beats requested/considered per gap tick (Q4 budget)
