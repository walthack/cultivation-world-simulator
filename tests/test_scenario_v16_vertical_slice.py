"""v1.6 vertical slice — the minimal real branching content, run end-to-end.

The closeout's missing piece: not a synthetic single-dispatch fixture, but a
real authored branch tree taken through the WHOLE pipeline —

    1 branch-point → 2 storylines → 2-3 beats each → run the full branch.

It is (1) loaded through the production loader so it must pass structural
validation (_validate_storyline_structure), and (2) dispatched month-by-month
through the production phase for BOTH choices, proving the chosen line's beats
all fire across months while the other line stays fully suppressed.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from src.scenario.scenario_loader import load
from src.scenario.state import ScriptedScenarioState
from src.sim.simulator_engine.phases.scripted_scenario import phase_scripted_scenario_tick
from src.systems.time import Month, Year, create_month_stamp


MONTHS = [Month.JANUARY, Month.FEBRUARY, Month.MARCH, Month.APRIL]


def _beat(event_id, storyline, month):
    return {
        "id": event_id,
        "type": "side_event",
        "storyline": storyline,
        "trigger": {"year": 1, "month": month, "condition": {"always": {}}},
        "effects": [{"type": "set_flag", "flag": f"{event_id}_seen"}],
    }


def _slice_timeline():
    return {
        "schema_version": "0.2",
        "events": [
            {
                "id": "fork",
                "type": "branch",
                "trigger": {"year": 1, "month": 1, "condition": {"always": {}}},
                "branches": [
                    {"id": "sun", "condition": {"world_flag": {"flag": "choose_sun"}},
                     "effects": [{"type": "activate_storyline", "storyline": "path_sun"}]},
                    {"id": "moon", "condition": {"world_flag": {"flag": "choose_moon"}},
                     "effects": [{"type": "activate_storyline", "storyline": "path_moon"}]},
                ],
            },
            _beat("sun-1", "path_sun", 2), _beat("sun-2", "path_sun", 3), _beat("sun-3", "path_sun", 4),
            _beat("moon-1", "path_moon", 2), _beat("moon-2", "path_moon", 3), _beat("moon-3", "path_moon", 4),
        ],
    }


def _write_slice(tmp_path):
    scenario = {
        "schema_version": "0.2", "scenario_id": "vslice", "title": "Vertical Slice",
        "version": "1.0", "author": "Test", "description": "branching vertical slice",
        "world_preset": {"preset_id": "default"},
        "initial_state": {"year": 1, "month": 1, "avatars": [], "relationships": [], "sects": [], "world_flags": {}},
    }
    d = tmp_path / "vslice"
    d.mkdir()
    (d / "scenario.json").write_text(json.dumps(scenario), encoding="utf-8")
    (d / "timeline.json").write_text(json.dumps(_slice_timeline()), encoding="utf-8")
    return d


async def _run_full_branch(world, timeline, choice_flag):
    """Run months 1-4 through the production phase; return the set of fired ids."""
    world.world_flags.clear()
    world.scripted_scenario = ScriptedScenarioState(
        scenario_id="vslice",
        timeline=timeline,
        state={"world_flags": {choice_flag: True}},
    )
    fired: list[str] = []
    for month in MONTHS:
        ctx = SimpleNamespace(month_stamp=create_month_stamp(Year(1), month))
        events = await phase_scripted_scenario_tick(world, ctx)
        fired.extend(e.id for e in events)
    return fired


def test_vertical_slice_loads_through_structural_validation(tmp_path):
    # Loading exercises _validate_storyline_structure — the slice must be well-formed.
    _write_slice(tmp_path)
    resolved = load("vslice", scenarios_root=tmp_path)
    assert len(resolved.timeline) == 7


@pytest.mark.asyncio
async def test_sun_branch_runs_to_completion_and_suppresses_moon(base_world):
    fired = await _run_full_branch(base_world, _slice_timeline()["events"], "choose_sun")

    assert fired == ["fork", "sun-1", "sun-2", "sun-3"]
    assert not any(eid.startswith("moon") for eid in fired)


@pytest.mark.asyncio
async def test_moon_branch_runs_to_completion_and_suppresses_sun(base_world):
    fired = await _run_full_branch(base_world, _slice_timeline()["events"], "choose_moon")

    assert fired == ["fork", "moon-1", "moon-2", "moon-3"]
    assert not any(eid.startswith("sun") for eid in fired)
