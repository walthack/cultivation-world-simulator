"""v1.9 M0 — the L4 Narrative Director bootstrap gate.

L4 inverts L3: the director proposes plot beyond the anchors. M0 builds the
proposal boundary + the forward-replay harness, but restricts the director to
SCOPED FACTS (zero mechanical read-back), so it provably cannot perturb a mandatory
anchor. The gate proves, NON-VACUOUSLY, that with the director ON the mandatory
anchors still fire at the same months as with it OFF — the harness that M1+ will
reuse once bounded-hard authority opens. Bounded-hard commands are rejected here.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.scenario.narrative_director import (
    DIRECTOR_COMMAND_WHITELIST,
    validate_director_proposal,
)
from src.scenario.state import ScriptedScenarioState
from src.sim.simulator_engine.phases.scripted_scenario import phase_scripted_scenario_tick
from src.systems.time import Month, Year, create_month_stamp


MONTHS = [Month.JANUARY, Month.FEBRUARY, Month.MARCH, Month.APRIL]
MANDATORY = {"m1", "m2"}


def _timeline():
    return [
        {"id": "m1", "anchor": True, "mandatory": True, "trigger": {"year": 1, "month": 1, "condition": {"always": {}}}},
        {"id": "m2", "anchor": True, "mandatory": True, "trigger": {"year": 1, "month": 4, "condition": {"always": {}}}},
    ]


def _director(proposals):
    """A director that, on its first invocation, returns the given proposals."""
    state = {"calls": 0}

    def gen(snapshot):
        state["calls"] += 1
        return proposals if state["calls"] == 1 else []

    gen.state = state  # type: ignore[attr-defined]
    return gen


async def _run(base_world, *, director):
    base_world.world_flags.clear()
    if director is not None:
        base_world.director_generator = director
    elif hasattr(base_world, "director_generator"):
        del base_world.director_generator
    base_world.scripted_scenario = ScriptedScenarioState(scenario_id="d0", timeline=_timeline())

    fired_at: dict[str, tuple[int, int]] = {}
    director_events = []
    for month in MONTHS:
        stamp = create_month_stamp(Year(1), month)
        base_world.month_stamp = stamp
        for ev in await phase_scripted_scenario_tick(base_world, SimpleNamespace(month_stamp=stamp)):
            if ev.id in MANDATORY:
                fired_at[ev.id] = (1, int(month.value))
            elif ev.narration is not None:
                director_events.append(ev)
    return fired_at, director_events


# --- proposal validation ------------------------------------------------------


def test_bootstrap_whitelist_is_scoped_facts_only():
    assert DIRECTOR_COMMAND_WHITELIST == {"director_fact"}


def test_pure_narration_proposal_is_accepted():
    assert validate_director_proposal({"id": "p", "narration": "..."}) == (True, None)


def test_bounded_hard_commands_are_rejected_in_bootstrap():
    for cmd in ({"command": "set_flag", "flag": "x"}, {"command": "world_event_trigger", "event_id": "e"}, {"command": "npc_die", "npc_id": "n"}):
        accepted, reason = validate_director_proposal({"command": cmd})
        assert not accepted and "whitelist" in reason


# --- the forward-replay gate --------------------------------------------------


@pytest.mark.asyncio
async def test_mandatory_anchors_fire_identically_with_director_on_vs_off(base_world):
    off, _ = await _run(base_world, director=None)
    on, _ = await _run(base_world, director=_director([
        {"id": "p1", "narration": "导演叙事", "command": {"command": "director_fact", "text": "程宗扬声名渐起"}},
    ]))
    assert set(off) == MANDATORY
    assert on == off  # the director (scoped facts) never perturbs mandatory anchors


@pytest.mark.asyncio
async def test_on_run_is_non_vacuous(base_world):
    director = _director([
        {"id": "p1", "narration": "市井议论纷纷", "command": {"command": "director_fact", "text": "传闻四起"}},
    ])
    _, director_events = await _run(base_world, director=director)

    # WITNESS: the director was invoked, accepted a proposal, recorded a scoped fact
    assert director.state["calls"] >= 1
    assert any(e.narration == "市井议论纷纷" for e in director_events)
    sc = base_world.scripted_scenario
    assert any(r["accepted"] and r.get("fact") == "传闻四起" for r in sc.director_ledger)
    assert all(e.id.startswith("director:") for e in director_events)


def _sentinel_timeline(m2_condition):
    # modellable event type (side_event = plain top-level effects) so the gate's
    # bounded dry-run can replay these mandatory anchors rather than fail closed.
    return [
        {"id": "m1", "type": "side_event", "anchor": True, "mandatory": True, "trigger": {"year": 1, "month": 1, "condition": {"always": {}}}},
        {"id": "m2", "type": "side_event", "anchor": True, "mandatory": True, "trigger": {"year": 1, "month": 4, "condition": m2_condition}},
    ]


async def _run_timeline(base_world, timeline, director):
    base_world.world_flags.clear()
    base_world.director_generator = director
    base_world.scripted_scenario = ScriptedScenarioState(scenario_id="m1", timeline=timeline)
    fired: set[str] = set()
    for month in MONTHS:
        stamp = create_month_stamp(Year(1), month)
        base_world.month_stamp = stamp
        for ev in await phase_scripted_scenario_tick(base_world, SimpleNamespace(month_stamp=stamp)):
            if ev.id in MANDATORY:
                fired.add(ev.id)
    return fired


@pytest.mark.asyncio
async def test_reachability_gate_rejects_a_flag_that_would_starve_a_mandatory_anchor(base_world):
    # m2 fires only while "blocker" is unset. director_set_flag(blocker) is now
    # WHITELISTED — but the forward-replay gate replays and sees m2 would be starved,
    # so it rejects the command. m2 still fires; the flag is never set.
    fired = await _run_timeline(
        base_world,
        _sentinel_timeline({"world_flag": {"flag": "blocker", "value": False}}),
        _director([{"id": "x", "narration": "试图设阻", "command": {"command": "director_set_flag", "flag": "blocker"}}]),
    )
    assert fired == MANDATORY
    assert "blocker" not in base_world.world_flags
    sc = base_world.scripted_scenario
    assert any(not r["accepted"] and "mandatory" in r.get("reason", "") for r in sc.director_ledger)


@pytest.mark.asyncio
async def test_reachability_gate_allows_a_flag_no_mandatory_anchor_reads(base_world):
    # a harmless flag (no mandatory condition reads it) passes the gate → applied.
    fired = await _run_timeline(
        base_world,
        _sentinel_timeline({"always": {}}),
        _director([{"id": "ok", "narration": "传闻渐起", "command": {"command": "director_set_flag", "flag": "rumor"}}]),
    )
    assert fired == MANDATORY
    assert base_world.world_flags.get("rumor") is True       # gate passed → real effect applied
    sc = base_world.scripted_scenario
    assert any(r["accepted"] and r.get("command", {}).get("flag") == "rumor" for r in sc.director_ledger)


@pytest.mark.asyncio
async def test_reachability_gate_fails_closed_on_a_non_modellable_horizon(base_world):
    # a horizon event with a non-modellable predicate (player_stat) → the gate can't
    # prove reachability → fail closed → even a harmless director flag is rejected.
    timeline = _sentinel_timeline({"always": {}})
    timeline.append({"id": "b", "type": "side_event", "trigger": {"year": 1, "month": 2, "condition": {"player_stat": {"stat": "qi", "value": 5}}}})
    fired = await _run_timeline(
        base_world, timeline,
        _director([{"id": "ok", "narration": "传闻", "command": {"command": "director_set_flag", "flag": "rumor"}}]),
    )
    assert fired == MANDATORY
    assert "rumor" not in base_world.world_flags             # fail-closed → not applied


@pytest.mark.asyncio
async def test_gate_fails_closed_on_a_branch_event_in_horizon(base_world):
    # branch dispatch (selection / default_branch) isn't modelled → fail closed
    timeline = _sentinel_timeline({"always": {}})
    timeline.append({"id": "bp", "type": "branch", "trigger": {"year": 1, "month": 2, "condition": {"always": {}}},
                     "branches": [{"id": "x", "condition": {"always": {}}, "effects": []}], "default_branch": "x"})
    fired = await _run_timeline(
        base_world, timeline,
        _director([{"id": "ok", "narration": "传闻", "command": {"command": "director_set_flag", "flag": "rumor"}}]),
    )
    assert fired == MANDATORY
    assert "rumor" not in base_world.world_flags


@pytest.mark.asyncio
async def test_gate_fails_closed_on_relation_change_shorthand_in_horizon(base_world):
    # relation_change synthesizes effects from a/b/delta — handler shorthand not
    # modelled by "apply top-level effects" → fail closed
    timeline = _sentinel_timeline({"always": {}})
    timeline.append({"id": "rc", "type": "relation_change", "a": "x", "b": "y", "delta": 3,
                     "trigger": {"year": 1, "month": 2, "condition": {"always": {}}}})
    fired = await _run_timeline(
        base_world, timeline,
        _director([{"id": "ok", "narration": "传闻", "command": {"command": "director_set_flag", "flag": "rumor"}}]),
    )
    assert fired == MANDATORY
    assert "rumor" not in base_world.world_flags


@pytest.mark.asyncio
async def test_director_events_are_story_and_empty_content_so_chronicle_excludes_them(base_world):
    # director events must carry the properties that the exclude_story chronicle
    # query relies on, so a burst of them can't crowd out authored facts.
    _, director_events = await _run(base_world, director=_director([
        {"id": "p", "narration": "导演事实", "command": {"command": "director_fact", "text": "t"}},
    ]))
    assert director_events
    assert all(e.is_story and (e.content or "") == "" for e in director_events)


@pytest.mark.asyncio
async def test_rejected_proposal_records_reason_and_emits_no_event(base_world):
    _, director_events = await _run(base_world, director=_director([
        {"id": "bad", "narration": "越权", "command": {"command": "set_flag", "flag": "x"}},
    ]))
    assert director_events == []  # rejected → no event
    sc = base_world.scripted_scenario
    bad = next(r for r in sc.director_ledger if r["proposal_id"] == "bad")
    assert not bad["accepted"] and "whitelist" in bad["reason"]
    assert "x" not in base_world.world_flags  # nothing mechanical happened
