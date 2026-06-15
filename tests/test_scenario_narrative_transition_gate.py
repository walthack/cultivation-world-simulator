"""v1.8 M0 — the L3 narrative-transition gate.

Anchors (events with ``anchor: true``) are the deterministic backbone. Between
anchors an injectable transition generator may propose narrative beats; each beat
carries render-only prose (-> ``Event.narration``) plus AT MOST one bounded,
whitelisted mechanical command. The core invariant is WRITE-SET NON-INTERFERENCE:
a beat's write set must not intersect the read set of ANY pending anchor
precondition, so a beat can never starve a scheduled anchor.

This is the gate: every anchor must fire at the same (year, month) whether
transitions are on or off. M1+ generation cannot ship until this passes — and the
"on" run must be proven NON-VACUOUS (a beat was actually generated, accepted, and
applied a nonzero effect), otherwise the differential is trivially green.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.scenario.narrative_transition import (
    PROTECT_ALL,
    TRANSITION_COMMAND_WHITELIST,
    command_write_set,
    condition_read_set,
    pending_anchor_read_set,
    validate_beat,
)
from src.scenario.state import ScriptedScenarioState
from src.scenario.state_access import get_relation
from src.sim.simulator_engine.phases.scripted_scenario import phase_scripted_scenario_tick
from src.systems.time import Month, Year, create_month_stamp


MONTHS = [Month.JANUARY, Month.FEBRUARY, Month.MARCH, Month.APRIL]
ANCHOR_IDS = {"a1-open", "a2-gate"}


def _timeline():
    # A2 fires only while the hero<->rival relation stays <= 0. That relation pair
    # is therefore PROTECTED: any beat touching it must be rejected, or A2 starves.
    return [
        {
            "id": "a1-open",
            "type": "side_event",
            "anchor": True,
            "trigger": {"year": 1, "month": 1, "condition": {"always": {}}},
            "effects": [{"type": "set_flag", "flag": "opened"}],
        },
        {
            "id": "a2-gate",
            "type": "side_event",
            "anchor": True,
            "trigger": {
                "year": 1,
                "month": 4,
                "condition": {"npc_relation": {"a": "hero", "b": "rival", "value": 0, "op": "<="}},
            },
            "effects": [{"type": "set_flag", "flag": "gated"}],
        },
    ]


def _stub_generator():
    """Returns three beats on its FIRST call only (so the witness is exact):
    one allowed (free relation pair), one forbidden by whitelist, one forbidden
    by write-set interference with A2's protected (hero, rival) pair."""
    state = {"calls": 0}

    def generate(snapshot):
        state["calls"] += 1
        if state["calls"] > 1:
            return []
        return [
            {  # allowed: touches a pair no pending anchor reads
                "id": "beat-allowed",
                "narration": "市井间，少侠与货商相谈甚欢。",
                "command": {"command": "relation_delta", "a": "hero", "b": "merchant", "delta": 5},
            },
            {  # forbidden by whitelist: flags are excluded from the Q2 whitelist
                "id": "beat-flag",
                "narration": "（试图设置 flag）",
                "command": {"command": "set_flag", "flag": "sneaky"},
            },
            {  # forbidden by write-set: would starve A2 (reads hero<->rival)
                "id": "beat-starve",
                "narration": "（试图拉高宿敌关系）",
                "command": {"command": "relation_delta", "a": "hero", "b": "rival", "delta": 5},
            },
        ]

    generate.state = state  # type: ignore[attr-defined]
    return generate


async def _run(base_world, *, generator):
    base_world.world_flags.clear()
    if generator is not None:
        base_world.transition_generator = generator
    elif hasattr(base_world, "transition_generator"):
        del base_world.transition_generator
    base_world.scripted_scenario = ScriptedScenarioState(scenario_id="m0", timeline=_timeline())

    fired_at: dict[str, tuple[int, int]] = {}
    beats: list = []
    for month in MONTHS:
        stamp = create_month_stamp(Year(1), month)
        base_world.month_stamp = stamp
        ctx = SimpleNamespace(month_stamp=stamp)
        events = await phase_scripted_scenario_tick(base_world, ctx)
        for ev in events:
            if ev.id in ANCHOR_IDS:
                fired_at[ev.id] = (1, int(month.value))
            elif ev.narration is not None:
                beats.append(ev)

    sc = base_world.scripted_scenario
    mech = {
        "world_flags": dict(base_world.world_flags),
        "state": dict(sc.state),
        "triggered": sorted(sc.triggered_events),
        "anchor_fire_months": dict(fired_at),
    }
    return mech, beats


# --- unit-level: the read-set / write-set extractors the invariant rests on ---


def test_condition_read_set_extracts_relation_and_flag_and_var():
    cond = {
        "all": [
            {"npc_relation": {"a": "hero", "b": "rival", "value": 0}},
            {"world_flag": {"flag": "north_pact"}},
            {"var_equals": {"name": "line", "value": "A"}},
        ]
    }
    rs = condition_read_set(cond)
    assert ("relation", frozenset({"hero", "rival"})) in rs
    assert ("flag", "north_pact") in rs
    assert ("var", "line") in rs


def test_command_write_set_relation_delta_is_orderless_pair():
    ws = command_write_set({"command": "relation_delta", "a": "rival", "b": "hero", "delta": 3})
    assert ws == {("relation", frozenset({"hero", "rival"}))}


def test_set_flag_is_not_whitelisted():
    assert "relation_delta" in TRANSITION_COMMAND_WHITELIST
    assert "set_flag" not in TRANSITION_COMMAND_WHITELIST


def test_read_set_is_fail_closed_for_unmodellable_predicates():
    # an unknown / mod predicate cannot be modelled → PROTECT_ALL (reject all beats)
    assert condition_read_set({"some_mod_predicate": {"x": 1}}) == {PROTECT_ALL}
    # var_equals over a structural sub-object a command can mutate → PROTECT_ALL
    assert condition_read_set({"var_equals": {"name": "relations", "value": {}}}) == {PROTECT_ALL}
    # malformed expression → PROTECT_ALL
    assert condition_read_set({"a": 1, "b": 2}) == {PROTECT_ALL}
    # relation-inert predicate a relation_delta can never affect → empty
    assert condition_read_set({"player_realm": {"realm": "CORE_FORMATION"}}) == set()


def test_protect_all_rejects_every_stateful_beat():
    beat = {"command": {"command": "relation_delta", "a": "x", "b": "y", "delta": 1}}
    accepted, reason = validate_beat(beat, {PROTECT_ALL})
    assert not accepted and "intersect" in reason
    # but a pure-narration beat (no command) is still fine even under PROTECT_ALL
    assert validate_beat({"narration": "..."}, {PROTECT_ALL}) == (True, None)


def test_validate_beat_rejects_malformed_relation_deltas():
    base = {"command": "relation_delta", "a": "x", "b": "y", "delta": 3}
    bad = [
        {**base, "a": ""},                 # empty endpoint
        {**base, "b": None},               # missing endpoint
        {**base, "a": "x", "b": "x"},      # same endpoint
        {**base, "delta": 0},              # no-op
        {**base, "delta": True},           # bool is not an int delta
        {**base, "delta": 1.5},            # float is not an int delta
        {**base, "delta": 99},             # over the bound
    ]
    for cmd in bad:
        accepted, reason = validate_beat({"command": cmd}, set())
        assert not accepted, cmd
        assert reason


def test_closure_protects_required_event_conditions_not_just_the_anchor():
    # A2's OWN condition is `always` (empty read-set), but it requires R whose
    # condition reads (hero, rival). A beat touching that pair would break R → A2
    # starves. The protected set must include R's reads via the closure.
    timeline = [
        {"id": "a1", "anchor": True, "trigger": {"year": 1, "month": 1, "condition": {"always": {}}}},
        {"id": "r", "trigger": {"year": 1, "month": 3, "condition": {"npc_relation": {"a": "hero", "b": "rival", "value": 0, "op": "<="}}}},
        {"id": "a2", "anchor": True, "requires_events": ["r"], "trigger": {"year": 1, "month": 4, "condition": {"always": {}}}},
    ]
    protected = pending_anchor_read_set(timeline, {"a1"}, player_id="p", now=(1, 2))
    assert ("relation", frozenset({"hero", "rival"})) in protected
    # a beat touching the required event's pair is therefore rejected
    starving = {"command": {"command": "relation_delta", "a": "hero", "b": "rival", "delta": 1}}
    assert validate_beat(starving, protected)[0] is False


def test_closure_protects_storyline_activator_conditions():
    # the anchor is gated by storyline "line-a"; its activator's condition reads
    # (hero, elder). A beat breaking that would stop activation → anchor starves.
    timeline = [
        {"id": "act", "type": "branch", "trigger": {"year": 1, "month": 1, "condition": {"npc_relation": {"a": "hero", "b": "elder", "value": 0}}},
         "effects": [{"type": "activate_storyline", "storyline": "line-a"}]},
        {"id": "anc", "anchor": True, "storyline": "line-a", "trigger": {"year": 1, "month": 5, "condition": {"always": {}}}},
    ]
    protected = pending_anchor_read_set(timeline, set(), player_id="p", now=(1, 2))
    assert ("relation", frozenset({"hero", "elder"})) in protected


def test_pending_read_set_resolves_player_and_skips_past_due_anchors():
    timeline = [
        {  # future player_relation anchor: protects (real_player, rival)
            "id": "future",
            "anchor": True,
            "trigger": {"year": 1, "month": 5, "condition": {"player_relation": {"npc_id": "rival", "value": 0}}},
        },
        {  # past-due unfired anchor: NOT protectable anymore
            "id": "missed",
            "anchor": True,
            "trigger": {"year": 1, "month": 2, "condition": {"npc_relation": {"a": "hero", "b": "elder", "value": 0}}},
        },
    ]
    reads = pending_anchor_read_set(timeline, set(), player_id="player-7", now=(1, 3))
    assert ("relation", frozenset({"player-7", "rival"})) in reads  # @player resolved
    assert ("relation", frozenset({"hero", "elder"})) not in reads   # past-due skipped


# --- the gate: anchors fire identically, with a NON-VACUOUS "on" run ---


@pytest.mark.asyncio
async def test_anchors_fire_identically_with_transitions_on_vs_off(base_world):
    mech_off, _ = await _run(base_world, generator=None)
    mech_on, _ = await _run(base_world, generator=_stub_generator())

    # both anchors fire at the SAME (year, month) regardless of transitions
    assert set(mech_off["anchor_fire_months"]) == ANCHOR_IDS
    assert mech_on["anchor_fire_months"] == mech_off["anchor_fire_months"]


@pytest.mark.asyncio
async def test_on_run_is_non_vacuous_and_protected_pair_untouched(base_world):
    gen = _stub_generator()
    mech_on, beats = await _run(base_world, generator=gen)

    # WITNESS: the generator was actually invoked and an allowed beat applied a
    # nonzero, bounded relation delta on the FREE pair.
    assert gen.state["calls"] >= 1
    relations = mech_on["state"].get("relations", {})
    assert get_relation(mech_on["state"], "hero", "merchant") == 5
    assert any(b.id == "beat-allowed" for b in beats)

    # the protected (hero, rival) pair A2 reads was never moved by a rejected beat
    assert get_relation(mech_on["state"], "hero", "rival") == 0
    # the whitelist-violating beat never set its flag
    assert "sneaky" not in mech_on["world_flags"]


@pytest.mark.asyncio
async def test_ledger_records_accept_and_reject_with_reasons_and_no_event(base_world):
    await _run(base_world, generator=_stub_generator())
    ledger = base_world.scripted_scenario.transition_ledger
    by_beat = {r["beat_id"]: r for r in ledger}

    assert by_beat["beat-allowed"]["accepted"] is True
    # whitelist rejection
    assert by_beat["beat-flag"]["accepted"] is False
    assert "whitelist" in by_beat["beat-flag"]["reason"]
    # write-set (starvation) rejection
    assert by_beat["beat-starve"]["accepted"] is False
    assert "intersect" in by_beat["beat-starve"]["reason"]


@pytest.mark.asyncio
async def test_forbidden_beats_emit_no_event(base_world):
    _, beats = await _run(base_world, generator=_stub_generator())
    emitted = {b.id for b in beats}
    assert emitted == {"beat-allowed"}  # rejected beats never become events


@pytest.mark.asyncio
async def test_generator_is_only_invoked_on_gap_ticks(base_world):
    seen_months: list[int] = []

    def spy(snapshot):
        seen_months.append(snapshot["month"])
        return []

    await _run(base_world, generator=spy)
    # anchors fire at M1 and M4; generation happens ONLY in the gap (M2, M3),
    # never on an anchor month or before the first anchor.
    assert seen_months == [2, 3]


@pytest.mark.asyncio
async def test_cadence_throttles_generation_within_a_long_gap(base_world):
    # anchors at M1 and M8 → gap = M2..M7. With cadence=3 the generator is asked at
    # M2, then not until M5, then M8 is an anchor month → seen = [2, 5].
    seen: list[int] = []

    def spy(snapshot):
        seen.append(snapshot["month"])
        return []

    base_world.world_flags.clear()
    base_world.transition_generator = spy
    base_world.transition_cadence_months = 3
    base_world.scripted_scenario = ScriptedScenarioState(
        scenario_id="m2",
        timeline=[
            {"id": "a1", "anchor": True, "trigger": {"year": 1, "month": 1, "condition": {"always": {}}}},
            {"id": "a2", "anchor": True, "trigger": {"year": 1, "month": 8, "condition": {"always": {}}}},
        ],
    )
    for m in range(1, 9):
        stamp = create_month_stamp(Year(1), Month(m))
        base_world.month_stamp = stamp
        await phase_scripted_scenario_tick(base_world, SimpleNamespace(month_stamp=stamp))

    assert seen == [2, 5]


@pytest.mark.asyncio
async def test_cadence_arithmetic_spans_a_year_boundary(base_world):
    # anchors at Y1M11 and Y2M3; gap = Y1M12, Y2M1, Y2M2. cadence=2 → call at
    # Y1M12 (total 24), skip Y2M1 (25-24=1), call Y2M2 (26-24=2). Proves
    # year*12+month month-diff is correct across the year boundary.
    seen: list[tuple[int, int]] = []

    def spy(snapshot):
        seen.append((snapshot["year"], snapshot["month"]))
        return []

    base_world.world_flags.clear()
    base_world.transition_generator = spy
    base_world.transition_cadence_months = 2
    base_world.scripted_scenario = ScriptedScenarioState(
        scenario_id="m2y",
        timeline=[
            {"id": "a1", "anchor": True, "trigger": {"year": 1, "month": 11, "condition": {"always": {}}}},
            {"id": "a2", "anchor": True, "trigger": {"year": 2, "month": 3, "condition": {"always": {}}}},
        ],
    )
    for yr, mo in [(1, 11), (1, 12), (2, 1), (2, 2), (2, 3)]:
        stamp = create_month_stamp(Year(yr), Month(mo))
        base_world.month_stamp = stamp
        await phase_scripted_scenario_tick(base_world, SimpleNamespace(month_stamp=stamp))

    assert seen == [(1, 12), (2, 2)]


@pytest.mark.asyncio
async def test_a_failed_generation_still_advances_the_cadence_cursor(base_world):
    # a generator failure must not let the next month re-invoke immediately
    # (no failure-driven hammering): cadence=2, generator raises at M2 → M3 skipped.
    calls: list[int] = []

    def boom(snapshot):
        calls.append(snapshot["month"])
        raise RuntimeError("provider down")

    base_world.world_flags.clear()
    base_world.transition_generator = boom
    base_world.transition_cadence_months = 2
    base_world.scripted_scenario = ScriptedScenarioState(
        scenario_id="m2f",
        timeline=[
            {"id": "a1", "anchor": True, "trigger": {"year": 1, "month": 1, "condition": {"always": {}}}},
            {"id": "a2", "anchor": True, "trigger": {"year": 1, "month": 4, "condition": {"always": {}}}},
        ],
    )
    for m in (1, 2, 3, 4):
        stamp = create_month_stamp(Year(1), Month(m))
        base_world.month_stamp = stamp
        await phase_scripted_scenario_tick(base_world, SimpleNamespace(month_stamp=stamp))

    assert calls == [2]  # M3 throttled despite the M2 failure


@pytest.mark.asyncio
async def test_cadence_cursor_round_trips_through_save_and_load(tmp_path):
    from unittest.mock import patch

    from src.classes.core.world import World
    from src.classes.environment.map import Map
    from src.classes.environment.tile import TileType
    from src.sim.load.load_game import load_game
    from src.sim.save.save_game import save_game
    from src.sim.simulator import Simulator

    def _map():
        m = Map(width=10, height=10)
        for x in range(10):
            for y in range(10):
                m.create_tile(x, y, TileType.PLAIN)
        return m

    world = World.create_with_db(
        map=_map(),
        month_stamp=create_month_stamp(Year(100), Month.JANUARY),
        events_db_path=tmp_path / "events.db",
    )
    world.scripted_scenario = ScriptedScenarioState(
        scenario_id="sample", timeline=[], transition_last_gen_month=1234
    )

    save_path = tmp_path / "save.json"
    ok, _ = save_game(world, Simulator(world), [], save_path)
    assert ok
    world.event_manager.close()

    with patch("src.run.load_map.load_cultivation_world_map", return_value=_map()):
        loaded, _, _ = load_game(save_path, active_scenario_id="sample")
    # the cadence cursor survives — reload won't reset the throttle and re-generate
    assert loaded.scripted_scenario.transition_last_gen_month == 1234


@pytest.mark.asyncio
async def test_off_run_never_invokes_generator_or_creates_beats(base_world):
    mech_off, beats = await _run(base_world, generator=None)

    assert beats == []
    # no transition touched relations at all
    assert mech_off["state"].get("relations", {}) == {}
