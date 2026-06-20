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
    _director_key,
    _run_locale,
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


async def _run_with_state(base_world, timeline, director, *, scenario_state=None):
    base_world.world_flags.clear()
    base_world.director_generator = director
    sc = ScriptedScenarioState(scenario_id="ph", timeline=timeline)
    if scenario_state:
        sc.state.update(scenario_state)
    base_world.scripted_scenario = sc
    fired: set[str] = set()
    for month in MONTHS:
        stamp = create_month_stamp(Year(1), month)
        base_world.month_stamp = stamp
        for ev in await phase_scripted_scenario_tick(base_world, SimpleNamespace(month_stamp=stamp)):
            if ev.id in MANDATORY:
                fired.add(ev.id)
    return fired


@pytest.mark.asyncio
async def test_gate_resolves_placeholder_when_controlled_avatar_present(base_world):
    # a horizon event with a {controlled_avatar} placeholder must replay through the
    # real apply_effects (production dispatch-state shape) — not crash. Here it's
    # harmless, so the safe director flag is allowed.
    timeline = _sentinel_timeline({"always": {}})
    timeline.append({"id": "ph", "type": "side_event", "trigger": {"year": 1, "month": 2, "condition": {"always": {}}},
                     "effects": [{"type": "set_flag", "flag": "seen_{controlled_avatar}"}]})
    fired = await _run_with_state(
        base_world, timeline,
        _director([{"id": "ok", "narration": "传闻", "command": {"command": "director_set_flag", "flag": "rumor"}}]),
        scenario_state={"controlled_avatar": "hero"},
    )
    assert fired == MANDATORY
    assert base_world.world_flags.get("rumor") is True       # gate ran cleanly → flag applied


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


# --- M1b: director_clear_flag + structured backbone gate (Q1/Q4) --------------


async def _run_backbone(base_world, *, timeline, director, backbone, preset_flags=None, scenario_state=None):
    base_world.world_flags.clear()
    if preset_flags:
        base_world.world_flags.update(preset_flags)
    base_world.director_generator = director
    sc = ScriptedScenarioState(scenario_id="bb", timeline=timeline, backbone=backbone)
    if scenario_state:
        sc.state.update(scenario_state)
    base_world.scripted_scenario = sc
    fired: set[str] = set()
    for month in MONTHS:
        stamp = create_month_stamp(Year(1), month)
        base_world.month_stamp = stamp
        for ev in await phase_scripted_scenario_tick(base_world, SimpleNamespace(month_stamp=stamp)):
            if ev.id in MANDATORY:
                fired.add(ev.id)
    return fired


def test_hard_command_whitelist_is_the_expected_set():
    from src.scenario.narrative_director import DIRECTOR_HARD_COMMAND_WHITELIST
    assert DIRECTOR_HARD_COMMAND_WHITELIST == {
        "director_set_flag", "director_clear_flag", "director_relation_change", "director_set_var",
        "director_introduce_minor_npc",
    }


def test_clear_flag_requires_a_non_empty_flag():
    accepted, reason = validate_director_proposal({"command": {"command": "director_clear_flag", "flag": ""}})
    assert not accepted and "flag" in reason


@pytest.mark.asyncio
async def test_backbone_irreversible_fact_blocks_clearing_a_death_flag(base_world):
    # "lin_dead" is an irreversible fact (a death). director_clear_flag(lin_dead) is a
    # RESURRECTION → the backbone gate rejects it; the flag survives.
    fired = await _run_backbone(
        base_world,
        timeline=_timeline(),
        director=_director([{"id": "res", "narration": "欲令死者复生", "command": {"command": "director_clear_flag", "flag": "lin_dead"}}]),
        backbone={"irreversible_facts": [{"world_flag": {"flag": "lin_dead", "value": True}}]},
        preset_flags={"lin_dead": True},
    )
    assert fired == MANDATORY
    assert base_world.world_flags.get("lin_dead") is True  # NOT resurrected
    sc = base_world.scripted_scenario
    assert any(not r["accepted"] and "irreversible" in r.get("reason", "") for r in sc.director_ledger)


@pytest.mark.asyncio
async def test_clear_flag_allowed_when_not_irreversible_and_no_mandatory_reads_it(base_world):
    # "rumor" isn't in the backbone and no mandatory anchor reads it → both gates pass,
    # the flag is really cleared.
    fired = await _run_backbone(
        base_world,
        timeline=_sentinel_timeline({"always": {}}),
        director=_director([{"id": "ok", "narration": "平息流言", "command": {"command": "director_clear_flag", "flag": "rumor"}}]),
        backbone={"irreversible_facts": [{"world_flag": {"flag": "lin_dead", "value": True}}]},
        preset_flags={"rumor": True},
    )
    assert fired == MANDATORY
    assert "rumor" not in base_world.world_flags  # gates passed → really cleared
    sc = base_world.scripted_scenario
    assert any(r["accepted"] and r.get("command", {}).get("command") == "director_clear_flag" for r in sc.director_ledger)


@pytest.mark.asyncio
async def test_backbone_prohibited_predicate_blocks_setting_a_forbidden_flag(base_world):
    # a sentinel (modellable) timeline so that, absent the backbone gate, the set would
    # pass reachability and wrongly apply. The prohibited predicate must reject it.
    fired = await _run_backbone(
        base_world,
        timeline=_sentinel_timeline({"always": {}}),
        director=_director([{"id": "evil", "narration": "魔头当道", "command": {"command": "director_set_flag", "flag": "demon_wins"}}]),
        backbone={"prohibited_predicates": [{"world_flag": {"flag": "demon_wins", "value": True}}]},
    )
    assert fired == MANDATORY
    assert "demon_wins" not in base_world.world_flags
    sc = base_world.scripted_scenario
    assert any(not r["accepted"] and "prohibited" in r.get("reason", "") for r in sc.director_ledger)


@pytest.mark.asyncio
async def test_director_flag_set_is_persisted_in_scenario_state(base_world):
    # the durable scenario-flag store is sc.state["world_flags"] (the only one saved);
    # a director set must land THERE, not just the ephemeral world.world_flags, or it
    # silently reverts on reload (codex P0). A persisted death flag is what makes an
    # irreversible fact actually irreversible across a save.
    await _run_backbone(
        base_world,
        timeline=_sentinel_timeline({"always": {}}),
        director=_director([{"id": "ok", "narration": "传闻渐起", "command": {"command": "director_set_flag", "flag": "rumor"}}]),
        backbone={},
    )
    sc = base_world.scripted_scenario
    assert sc.state.get("world_flags", {}).get("rumor") is True


@pytest.mark.asyncio
async def test_director_flag_clear_is_persisted_in_scenario_state(base_world):
    # a clear must also reach the durable store: a flag seeded in sc.state must be gone
    # from sc.state after the director clears it (not just the ephemeral copy).
    await _run_backbone(
        base_world,
        timeline=_sentinel_timeline({"always": {}}),
        director=_director([{"id": "ok", "narration": "平息流言", "command": {"command": "director_clear_flag", "flag": "rumor"}}]),
        backbone={},
        scenario_state={"world_flags": {"rumor": True}},
    )
    sc = base_world.scripted_scenario
    assert "rumor" not in sc.state.get("world_flags", {})


@pytest.mark.asyncio
async def test_backbone_gate_fails_closed_on_an_unevaluable_predicate(base_world):
    # a prohibited predicate the evaluator can't resolve (unknown npc) → the backbone
    # gate can't be evaluated → fail closed → even a harmless flag is rejected.
    fired = await _run_backbone(
        base_world,
        timeline=_sentinel_timeline({"always": {}}),
        director=_director([{"id": "ok", "narration": "传闻", "command": {"command": "director_set_flag", "flag": "rumor"}}]),
        backbone={"prohibited_predicates": [{"npc_alive": {"npc_id": "ghost"}}]},
    )
    assert fired == MANDATORY
    assert "rumor" not in base_world.world_flags  # fail-closed → not applied
    sc = base_world.scripted_scenario
    assert any(not r["accepted"] and "backbone" in r.get("reason", "") for r in sc.director_ledger)


# --- M1c: director_relation_change (3rd hard command) -------------------------


def test_relation_change_validation():
    ok = {"command": "director_relation_change", "a": "x", "b": "y", "delta": 5}
    assert validate_director_proposal({"command": ok}) == (True, None)
    # missing endpoints / non-int delta are rejected
    bad_cases = [
        {"command": "director_relation_change", "a": "", "b": "y", "delta": 5},
        {"command": "director_relation_change", "a": "x", "b": "y"},
        {"command": "director_relation_change", "a": "x", "b": "y", "delta": 1.5},
        {"command": "director_relation_change", "a": "x", "b": "y", "delta": True},
    ]
    for bad in bad_cases:
        accepted, reason = validate_director_proposal({"command": bad})
        assert not accepted and reason


@pytest.mark.asyncio
async def test_relation_change_rejected_when_it_would_starve_a_mandatory_anchor(base_world):
    # m2 fires only while rel(x,y) >= 10. A director relation_change of -20 would drop it
    # below the threshold → the reachability gate replays, sees m2 starved, rejects.
    fired = await _run_backbone(
        base_world,
        timeline=_sentinel_timeline({"npc_relation": {"a": "x", "b": "y", "value": 10, "op": ">="}}),
        director=_director([{"id": "rc", "narration": "挑拨离间", "command": {"command": "director_relation_change", "a": "x", "b": "y", "delta": -20}}]),
        backbone={},
        scenario_state={"relations": {"x:y": 10}},
    )
    assert fired == MANDATORY
    assert base_world.scripted_scenario.state["relations"]["x:y"] == 10  # unchanged
    sc = base_world.scripted_scenario
    assert any(not r["accepted"] and "mandatory" in r.get("reason", "") for r in sc.director_ledger)


@pytest.mark.asyncio
async def test_relation_change_allowed_persists_into_scenario_state(base_world):
    # no mandatory anchor reads this relation and no backbone forbids it → both gates
    # pass, the change is applied AND lands in the durable sc.state["relations"] even
    # though this scenario started with no "relations" key (the mirror covers that).
    await _run_backbone(
        base_world,
        timeline=_sentinel_timeline({"always": {}}),
        director=_director([{"id": "ok", "narration": "义结金兰", "command": {"command": "director_relation_change", "a": "x", "b": "y", "delta": 5}}]),
        backbone={},
    )
    sc = base_world.scripted_scenario
    assert sc.state.get("relations", {}).get("x:y") == 5
    assert any(r["accepted"] and r.get("command", {}).get("command") == "director_relation_change" for r in sc.director_ledger)


@pytest.mark.asyncio
async def test_relation_change_blocked_by_backbone_prohibited_predicate(base_world):
    # a prohibited predicate on the relation (>= 100) → a +200 swing would satisfy it
    # → backbone gate rejects; the relation stays put.
    await _run_backbone(
        base_world,
        timeline=_sentinel_timeline({"always": {}}),
        director=_director([{"id": "evil", "narration": "结成死党", "command": {"command": "director_relation_change", "a": "x", "b": "y", "delta": 200}}]),
        backbone={"prohibited_predicates": [{"npc_relation": {"a": "x", "b": "y", "value": 100, "op": ">="}}]},
        scenario_state={"relations": {"x:y": 0}},
    )
    sc = base_world.scripted_scenario
    assert sc.state["relations"]["x:y"] == 0  # unchanged
    assert any(not r["accepted"] and "prohibited" in r.get("reason", "") for r in sc.director_ledger)


# --- M1e: director_set_var (4th hard command) ---------------------------------


def test_set_var_validation():
    ok = {"command": "director_set_var", "name": "mood", "value": "tense"}
    assert validate_director_proposal({"command": ok}) == (True, None)
    for bad in (
        {"command": "director_set_var", "name": "", "value": "x"},
        {"command": "director_set_var", "name": "mood"},                 # no value
        {"command": "director_set_var", "name": "mood", "value": {"a": 1}},  # non-scalar
        {"command": "director_set_var", "name": "mood", "value": None},
    ):
        accepted, reason = validate_director_proposal({"command": bad})
        assert not accepted and reason


@pytest.mark.asyncio
async def test_set_var_rejected_when_it_would_starve_a_mandatory_anchor(base_world):
    # m2 fires only while var phase=="open"; a director set_var phase="closed" would
    # starve it → reachability gate rejects; the var is unchanged.
    fired = await _run_backbone(
        base_world,
        timeline=_sentinel_timeline({"var_equals": {"name": "phase", "value": "open"}}),
        director=_director([{"id": "v", "narration": "时局突变", "command": {"command": "director_set_var", "name": "phase", "value": "closed"}}]),
        backbone={},
        scenario_state={"phase": "open"},
    )
    assert fired == MANDATORY
    assert base_world.scripted_scenario.state["phase"] == "open"  # unchanged
    assert any(not r["accepted"] and "mandatory" in r.get("reason", "") for r in base_world.scripted_scenario.director_ledger)


@pytest.mark.asyncio
async def test_set_var_allowed_persists_into_scenario_state(base_world):
    # no mandatory reads `mood` and no backbone forbids it → applied; scenario vars live
    # in sc.state directly (no mirror needed).
    await _run_backbone(
        base_world,
        timeline=_sentinel_timeline({"always": {}}),
        director=_director([{"id": "ok", "narration": "气氛凝重", "command": {"command": "director_set_var", "name": "mood", "value": "tense"}}]),
        backbone={},
    )
    sc = base_world.scripted_scenario
    assert sc.state.get("mood") == "tense"
    assert any(r["accepted"] and r.get("command", {}).get("command") == "director_set_var" for r in sc.director_ledger)


@pytest.mark.asyncio
async def test_set_var_blocked_by_backbone_prohibited_predicate(base_world):
    # a prohibited predicate on a var → setting it to the forbidden value is rejected.
    await _run_backbone(
        base_world,
        timeline=_sentinel_timeline({"always": {}}),
        director=_director([{"id": "doom", "narration": "天倾", "command": {"command": "director_set_var", "name": "ending", "value": "doom"}}]),
        backbone={"prohibited_predicates": [{"var_equals": {"name": "ending", "value": "doom"}}]},
    )
    sc = base_world.scripted_scenario
    assert sc.state.get("ending") != "doom"
    assert any(not r["accepted"] and "prohibited" in r.get("reason", "") for r in sc.director_ledger)


# --- M1f: director_introduce_minor_npc (5th hard command) ---------------------


def test_introduce_minor_npc_validation():
    ok = {"command": "director_introduce_minor_npc", "id": "wanderer", "name": "无名游侠"}
    assert validate_director_proposal({"command": ok}) == (True, None)
    for bad in (
        {"command": "director_introduce_minor_npc", "id": "", "name": "x"},
        {"command": "director_introduce_minor_npc", "id": "x"},  # no name
    ):
        accepted, reason = validate_director_proposal({"command": bad})
        assert not accepted and reason


@pytest.mark.asyncio
async def test_introduce_minor_npc_allowed_persists_into_scenario_state(base_world):
    # a brand-new id no mandatory references → both gates pass; the npc lands durably in
    # sc.state["npcs"] (so future relation_change / entity_ids can use it).
    await _run_backbone(
        base_world,
        timeline=_sentinel_timeline({"always": {}}),
        director=_director([{"id": "intro", "narration": "市井来了个生面孔", "command": {"command": "director_introduce_minor_npc", "id": "stranger", "name": "陌生人"}}]),
        backbone={},
    )
    sc = base_world.scripted_scenario
    npc = sc.state.get("npcs", {}).get("stranger")
    assert npc and npc["name"] == "陌生人" and npc["alive"] is True
    assert any(r["accepted"] and r.get("command", {}).get("command") == "director_introduce_minor_npc" for r in sc.director_ledger)


@pytest.mark.asyncio
async def test_introduce_minor_npc_rejects_a_colliding_existing_id(base_world):
    # the director must not hijack an existing entity — a colliding id is rejected and
    # the existing npc is left untouched.
    await _run_backbone(
        base_world,
        timeline=_sentinel_timeline({"always": {}}),
        director=_director([{"id": "dup", "narration": "冒名顶替", "command": {"command": "director_introduce_minor_npc", "id": "hero", "name": "冒牌货"}}]),
        backbone={},
        scenario_state={"npcs": {"hero": {"id": "hero", "name": "主角", "alive": True}}},
    )
    sc = base_world.scripted_scenario
    assert sc.state["npcs"]["hero"]["name"] == "主角"  # untouched
    assert any(not r["accepted"] and "exists" in r.get("reason", "") for r in sc.director_ledger)


@pytest.mark.asyncio
async def test_introduce_minor_npc_fails_closed_when_a_mandatory_reads_npc_state(base_world):
    # a horizon mandatory whose condition reads npc state (npc_alive) is non-modellable in
    # the bounded dry-run (no npcs) → fail-closed → even a harmless new npc is rejected.
    fired = await _run_backbone(
        base_world,
        timeline=_sentinel_timeline({"npc_alive": {"npc_id": "hero"}}),
        director=_director([{"id": "intro", "narration": "新面孔", "command": {"command": "director_introduce_minor_npc", "id": "stranger", "name": "陌生人"}}]),
        backbone={},
        scenario_state={"npcs": {"hero": {"id": "hero", "name": "主角", "alive": True}}},
    )
    assert fired == MANDATORY
    assert "stranger" not in base_world.scripted_scenario.state.get("npcs", {})  # fail-closed → not added


# --- M2a: deterministic director replay (frozen cache) ------------------------


@pytest.mark.asyncio
async def test_director_turn_is_frozen_replayed_not_requeried_or_reapplied(base_world):
    # Re-running the SAME director month must hit the frozen cache: the generator is not
    # called again and the mechanical effect (relation +5) is NOT re-applied (no double).
    director = _director([{"id": "rc", "narration": "义结金兰", "command": {"command": "director_relation_change", "a": "x", "b": "y", "delta": 5}}])
    base_world.world_flags.clear()
    base_world.director_generator = director
    base_world.scripted_scenario = ScriptedScenarioState(scenario_id="rep", timeline=_sentinel_timeline({"always": {}}))
    stamp = create_month_stamp(Year(1), Month.JANUARY)
    base_world.month_stamp = stamp
    ctx = SimpleNamespace(month_stamp=stamp)

    ev1 = await phase_scripted_scenario_tick(base_world, ctx)
    ev2 = await phase_scripted_scenario_tick(base_world, ctx)  # SAME month → replay

    sc = base_world.scripted_scenario
    assert director.state["calls"] == 1                       # 2nd tick hit the cache
    assert sc.state["relations"]["x:y"] == 5                  # applied exactly once
    d1 = [e.id for e in ev1 if (e.id or "").startswith("director:")]
    d2 = [e.id for e in ev2 if (e.id or "").startswith("director:")]
    assert d1 and d2 == d1                                    # same frozen event replayed


@pytest.mark.asyncio
async def test_reloaded_director_cache_replays_without_calling_generator(base_world):
    # simulate a reload: a sc carrying a pre-frozen turn + a generator that explodes if
    # called. The cached turn must replay (narration only) without invoking the generator.
    stamp = create_month_stamp(Year(1), Month.JANUARY)
    base_world.month_stamp = stamp
    base_world.world_flags.clear()
    sc = ScriptedScenarioState(scenario_id="rl", timeline=_sentinel_timeline({"always": {}}))
    key = _director_key((1, 1), {}, _run_locale(base_world))
    sc.director_cache = {key: [{"engine_id": "director:1:1:0", "accepted": True, "narration": "旧事重提"}]}
    base_world.scripted_scenario = sc

    def boom(snapshot):
        raise AssertionError("generator must not be called on a cache hit")

    base_world.director_generator = boom
    events = await phase_scripted_scenario_tick(base_world, SimpleNamespace(month_stamp=stamp))
    replayed = [e.narration for e in events if (e.id or "").startswith("director:")]
    assert replayed == ["旧事重提"]


@pytest.mark.asyncio
async def test_frozen_turn_replays_even_with_no_generator_attached(base_world):
    # codex P1: a reload into an environment with NO generator must still replay the
    # frozen narration — the cache lookup precedes the generator guard.
    stamp = create_month_stamp(Year(1), Month.JANUARY)
    base_world.month_stamp = stamp
    base_world.world_flags.clear()
    sc = ScriptedScenarioState(scenario_id="ng", timeline=_sentinel_timeline({"always": {}}))
    key = _director_key((1, 1), {}, _run_locale(base_world))
    sc.director_cache = {key: [{"engine_id": "director:1:1:0", "accepted": True, "narration": "无导演亦重放"}]}
    base_world.scripted_scenario = sc
    if hasattr(base_world, "director_generator"):
        del base_world.director_generator  # no generator at all

    events = await phase_scripted_scenario_tick(base_world, SimpleNamespace(month_stamp=stamp))
    replayed = [e.narration for e in events if (e.id or "").startswith("director:")]
    assert replayed == ["无导演亦重放"]


# --- M3: director cadence throttle (Q9) ---------------------------------------


@pytest.mark.asyncio
async def test_director_cadence_throttles_generation(base_world):
    # with director_cadence_months=3 the director generates only every 3rd month
    # (months 1, 4, 7 over a 9-month run), not every month.
    calls = {"n": 0}

    def gen(snapshot):
        calls["n"] += 1
        return [{"id": f"b{calls['n']}", "narration": f"beat{calls['n']}"}]

    base_world.world_flags.clear()
    base_world.director_generator = gen
    base_world.director_cadence_months = 3
    base_world.scripted_scenario = ScriptedScenarioState(scenario_id="cad", timeline=_sentinel_timeline({"always": {}}))

    for month in list(Month)[:9]:
        stamp = create_month_stamp(Year(1), month)
        base_world.month_stamp = stamp
        await phase_scripted_scenario_tick(base_world, SimpleNamespace(month_stamp=stamp))

    assert calls["n"] == 3                                            # months 1, 4, 7 only
    assert base_world.scripted_scenario.director_last_gen_month == 1 * 12 + 7  # last gen at y1m7
