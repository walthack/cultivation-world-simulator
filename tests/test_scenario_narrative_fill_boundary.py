"""v1.7 M0 — the render-only boundary gate.

Generated narrative text lives on a dedicated render-only channel
(`Event.narration`) that NO mechanical consumer reads — not scenario state
(var_equals-readable), not `Event.content` (feeds AI memory + relation deltas),
not conditions/effects. This is the gate: enabling fill must leave the entire
mechanical projection byte-identical across ticks. M1+ generation cannot ship
until this passes.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.scenario.state import ScriptedScenarioState
from src.sim.simulator_engine.phases.scripted_scenario import phase_scripted_scenario_tick
from src.systems.time import Month, Year, create_month_stamp


MONTHS = [Month.JANUARY, Month.FEBRUARY]


def _timeline():
    return [
        {
            "id": "e1",
            "type": "side_event",
            "narrative_fill": True,
            "trigger": {"year": 1, "month": 1, "condition": {"always": {}}},
            "effects": [
                {"type": "set_flag", "flag": "f1"},
                {"type": "set_var", "name": "v1", "value": "mech"},
            ],
        },
        {
            "id": "e2",
            "type": "side_event",
            "trigger": {"year": 1, "month": 2, "condition": {"always": {}}},
            "effects": [{"type": "set_flag", "flag": "f2"}],
        },
    ]


def _stub_filler(scenario_event, world):
    return f"[fill:{scenario_event.get('id')}]"


async def _run(base_world, *, filler):
    base_world.world_flags.clear()
    if filler is not None:
        base_world.narrative_filler = filler
    base_world.scripted_scenario = ScriptedScenarioState(scenario_id="m0", timeline=_timeline())
    fired = []
    for month in MONTHS:
        ctx = SimpleNamespace(month_stamp=create_month_stamp(Year(1), month))
        fired.extend(await phase_scripted_scenario_tick(base_world, ctx))
    sc = base_world.scripted_scenario
    mech = {
        "world_flags": dict(base_world.world_flags),
        "state": dict(sc.state),  # scenario_vars / persisted state — narration must NOT be here
        "triggered": sorted(sc.triggered_events),
        "contents": [e.content for e in fired],  # feeds AI memory — must not carry fill
    }
    return mech, fired


@pytest.mark.asyncio
async def test_enabling_fill_does_not_perturb_mechanical_state(base_world):
    mech_off, off = await _run(base_world, filler=None)
    mech_on, on = await _run(base_world, filler=_stub_filler)

    # the entire mechanical projection is byte-identical with fill on vs off
    assert mech_on == mech_off


@pytest.mark.asyncio
async def test_fill_lands_only_on_the_render_only_channel_and_is_opt_in(base_world):
    _, fired = await _run(base_world, filler=_stub_filler)
    by_id = {e.id: e for e in fired}

    # opt-in event gets render-only narration; its mechanical content is untouched
    assert by_id["e1"].narration == "[fill:e1]"
    assert "[fill:" not in (by_id["e1"].content or "")
    # non-opt-in event is never filled
    assert by_id["e2"].narration is None


@pytest.mark.asyncio
async def test_no_filler_means_no_narration(base_world):
    _, fired = await _run(base_world, filler=None)

    assert all(e.narration is None for e in fired)
