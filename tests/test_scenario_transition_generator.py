"""v1.8 M4 — the production LLM-backed transition generator.

`make_transition_generator` turns the world-free snapshot into a prompt, calls the
JSON LLM, and parses `{"beats":[...]}`. It is resilient (any failure → []), the
prompt keeps the next-anchor target reserved (never truncated), and the phase
still validates every proposed beat — so a bad command from the model is rejected,
never applied.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.scenario.narrative_transition import (
    build_transition_prompt,
    make_transition_generator,
)
from src.scenario.state import ScriptedScenarioState
from src.scenario.state_access import get_relation
from src.sim.simulator_engine.phases.scripted_scenario import phase_scripted_scenario_tick
from src.systems.time import Month, Year, create_month_stamp


def _snap(**over):
    s = {
        "year": 1, "month": 2,
        "relations": {}, "pending_anchor_ids": ["a2"],
        "next_anchor_target": "决战在即", "context_block": "",
    }
    s.update(over)
    return s


# --- prompt assembly ----------------------------------------------------------


def test_prompt_reserves_the_next_anchor_target_even_under_huge_context():
    p = build_transition_prompt(_snap(context_block="噪声" * 50000))
    assert "决战在即" in p                  # reserved target survives
    assert "参考数据" in p                  # authored data is fenced as non-instruction


# --- generator parsing + resilience ------------------------------------------


@pytest.mark.asyncio
async def test_generator_parses_beats_from_llm_json():
    async def fake(prompt, mode):
        return {"beats": [{"id": "b", "narration": "市井流言", "command": {"command": "relation_delta", "a": "p", "b": "q", "delta": 2}}]}

    beats = await make_transition_generator(call_llm_json=fake)(_snap())
    assert len(beats) == 1 and beats[0]["narration"] == "市井流言"


@pytest.mark.asyncio
async def test_generator_degrades_to_empty_on_bad_shape_or_failure():
    async def no_beats(prompt, mode):
        return {"oops": 1}

    async def not_a_dict(prompt, mode):
        return [1, 2, 3]

    async def boom(prompt, mode):
        raise RuntimeError("provider down")

    for fake in (no_beats, not_a_dict, boom):
        assert await make_transition_generator(call_llm_json=fake)(_snap()) == []


@pytest.mark.asyncio
async def test_generator_drops_non_dict_beats():
    async def messy(prompt, mode):
        return {"beats": [{"id": "ok", "narration": "x"}, "junk", 42, None]}

    beats = await make_transition_generator(call_llm_json=messy)(_snap())
    assert beats == [{"id": "ok", "narration": "x"}]


# --- end-to-end through the phase --------------------------------------------


@pytest.mark.asyncio
async def test_production_generator_applies_a_validated_beat_through_the_phase(base_world):
    async def fake(prompt, mode):
        return {"beats": [
            {"id": "b1", "narration": "过场一", "command": {"command": "relation_delta", "a": "hero", "b": "merchant", "delta": 3}},
            {"id": "b2", "narration": "越界", "command": {"command": "set_flag", "flag": "x"}},  # rejected by phase
        ]}

    base_world.world_flags.clear()
    base_world.transition_generator = make_transition_generator(call_llm_json=fake)
    base_world.scripted_scenario = ScriptedScenarioState(
        scenario_id="gen",
        timeline=[
            {"id": "a1", "anchor": True, "trigger": {"year": 1, "month": 1, "condition": {"always": {}}}},
            {"id": "a2", "anchor": True, "trigger": {"year": 1, "month": 4, "condition": {"always": {}}}},
        ],
    )
    for m in (Month.JANUARY, Month.FEBRUARY):
        stamp = create_month_stamp(Year(1), m)
        base_world.month_stamp = stamp
        await phase_scripted_scenario_tick(base_world, SimpleNamespace(month_stamp=stamp))

    sc = base_world.scripted_scenario
    assert get_relation(sc.state, "hero", "merchant") == 3   # allowed beat applied
    assert "x" not in base_world.world_flags                 # set_flag beat rejected by the phase
