"""v1.6 storyline persistence across production ticks.

The isolated dispatcher tests only ever ran a single dispatch_month, so they
never caught that active storylines must survive between months. In the real
simulator each month rebuilds the dispatch state from ScriptedScenarioState;
if `active_storylines` is not part of the persisted state, a branch that
activates a storyline in month 1 cannot unlock that storyline's beats in
month 2 — the feature is silently dead in production.

This test crosses the production phase boundary (phase_scripted_scenario_tick).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.scenario.state import ScriptedScenarioState
from src.sim.simulator_engine.phases.scripted_scenario import phase_scripted_scenario_tick
from src.systems.time import Month, Year, create_month_stamp


def _ctx(year: int, month: Month):
    return SimpleNamespace(month_stamp=create_month_stamp(Year(year), month))


def _timeline():
    return [
        {
            "id": "fork",
            "type": "branch",
            "trigger": {"year": 1, "month": 1, "condition": {"always": {}}},
            "branches": [
                {"id": "line_a", "condition": {"always": {}},
                 "effects": [{"type": "activate_storyline", "storyline": "line_a"}]},
            ],
        },
        {
            "id": "line-a-beat",
            "type": "side_event",
            "storyline": "line_a",
            "trigger": {"year": 1, "month": 2, "condition": {"always": {}}},
            "effects": [{"type": "set_flag", "flag": "line_a_beat_seen"}],
        },
    ]


@pytest.mark.asyncio
async def test_storyline_activated_in_month1_unlocks_a_beat_in_month2(base_world):
    base_world.scripted_scenario = ScriptedScenarioState(
        scenario_id="persist_demo",
        timeline=_timeline(),
    )

    # month 1: the branch fires and activates storyline "line_a"
    m1 = await phase_scripted_scenario_tick(base_world, _ctx(1, Month.JANUARY))
    assert "fork" in [e.id for e in m1]

    # month 2: the storyline-tagged beat must fire because line_a is still active
    m2 = await phase_scripted_scenario_tick(base_world, _ctx(1, Month.FEBRUARY))

    assert "line-a-beat" in [e.id for e in m2]
    assert base_world.world_flags.get("line_a_beat_seen") is True
