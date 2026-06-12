"""v1.7 M1 — narration falls back to the authored static text (Q2/Q9).

A narrative_fill event always ends up with a narration: the LLM text when the
filler yields a non-empty string, otherwise the authored narration_fallback —
on no filler, filler failure, or empty output. A filler exception must never
break the tick.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.scenario.state import ScriptedScenarioState
from src.sim.simulator_engine.phases.scripted_scenario import phase_scripted_scenario_tick
from src.systems.time import Month, Year, create_month_stamp


FALLBACK = "程宗扬立于草原，秦军方阵未动。"


def _timeline():
    return [{
        "id": "e1",
        "type": "side_event",
        "narrative_fill": True,
        "narration_fallback": FALLBACK,
        "trigger": {"year": 1, "month": 1, "condition": {"always": {}}},
        "effects": [{"type": "set_flag", "flag": "f1"}],
    }]


async def _narration(base_world, filler):
    base_world.world_flags.clear()
    if filler is not None:
        base_world.narrative_filler = filler
    base_world.scripted_scenario = ScriptedScenarioState(scenario_id="fb", timeline=_timeline())
    ctx = SimpleNamespace(month_stamp=create_month_stamp(Year(1), Month.JANUARY))
    events = await phase_scripted_scenario_tick(base_world, ctx)
    return events[0].narration


@pytest.mark.asyncio
async def test_no_filler_uses_authored_fallback(base_world):
    assert await _narration(base_world, None) == FALLBACK


@pytest.mark.asyncio
async def test_filler_success_uses_generated_text(base_world):
    text = "草原风卷尘沙，他第一次看清这世界的凶险。"
    assert await _narration(base_world, lambda reqs, w: {"e1": text}) == text


@pytest.mark.asyncio
async def test_filler_returning_empty_uses_fallback(base_world):
    assert await _narration(base_world, lambda reqs, w: {"e1": "   "}) == FALLBACK
    assert await _narration(base_world, lambda reqs, w: {}) == FALLBACK  # omitted → fallback


@pytest.mark.asyncio
async def test_filler_exception_falls_back_without_breaking_tick(base_world):
    def boom(reqs, w):
        raise RuntimeError("llm down")

    assert await _narration(base_world, boom) == FALLBACK
