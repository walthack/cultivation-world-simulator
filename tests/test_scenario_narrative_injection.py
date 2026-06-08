import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.classes.long_term_objective import generate_long_term_objective
from src.classes.story_event_service import StoryEventKind, StoryEventService
from src.classes.story_teller import StoryTeller
from src.scenario.narrative_context import build_scenario_context_block
from src.scenario.state import ScriptedScenarioState


LIUCHAO_SCENARIO_PATH = Path("config/scenarios/liuchao/scenario.json")


def _liuchao_profile() -> dict:
    data = json.loads(LIUCHAO_SCENARIO_PATH.read_text(encoding="utf-8"))
    return data["initial_state"]["generation_profile"]


def _attach_liuchao_scenario(world) -> dict:
    profile = _liuchao_profile()
    world.scripted_scenario = ScriptedScenarioState(
        scenario_id="liuchao",
        timeline=[],
        generation_profile=profile,
    )
    return profile["narrative_context"]


def _assert_liuchao_context_present(text: str, context: dict) -> None:
    assert "Scenario narrative context:" in text
    assert context["background"] in text
    assert context["style"] in text
    assert context["terminology"] in text


def test_build_scenario_context_block_empty_without_scenario(base_world):
    assert build_scenario_context_block(base_world) == ""


def test_build_scenario_context_block_empty_without_generation_profile(base_world):
    base_world.scripted_scenario = ScriptedScenarioState(scenario_id="empty", timeline=[])
    assert build_scenario_context_block(base_world) == ""


def test_build_scenario_context_block_empty_without_narrative_context(base_world):
    base_world.scripted_scenario = ScriptedScenarioState(
        scenario_id="no_context",
        timeline=[],
        generation_profile={"generation_sources": {"npc_names": "scenario"}},
    )
    assert build_scenario_context_block(base_world) == ""


@pytest.mark.asyncio
async def test_liuchao_long_term_objective_prompt_contains_narrative_context(dummy_avatar):
    context = _attach_liuchao_scenario(dummy_avatar.world)

    with patch(
        "src.classes.long_term_objective.call_llm_with_task_name",
        new=AsyncMock(return_value={"long_term_objective": "入仕建功"}),
    ) as mock_llm:
        await generate_long_term_objective(dummy_avatar)

    infos = mock_llm.await_args.args[2]
    _assert_liuchao_context_present(infos["world_lore"], context)


@pytest.mark.asyncio
async def test_liuchao_story_teller_prompt_contains_narrative_context(dummy_avatar):
    context = _attach_liuchao_scenario(dummy_avatar.world)

    with patch(
        "src.classes.story_teller.call_llm_with_task_name",
        new=AsyncMock(return_value={"story": "短故事"}),
    ) as mock_llm:
        await StoryTeller.tell_story("州郡起事", "众人退守城中", dummy_avatar, prompt="保留原始提示")

    infos = mock_llm.await_args.args[2]
    _assert_liuchao_context_present(infos["story_prompt"], context)
    assert "保留原始提示" in infos["story_prompt"]


@pytest.mark.asyncio
async def test_liuchao_story_event_service_passes_narrative_context_to_teller(dummy_avatar):
    context = _attach_liuchao_scenario(dummy_avatar.world)

    with patch("src.classes.story_event_service.StoryEventService.should_trigger", return_value=True), patch(
        "src.classes.story_event_service.StoryTeller.tell_story",
        new=AsyncMock(return_value="故事正文"),
    ) as mock_tell:
        await StoryEventService.maybe_create_story(
            kind=StoryEventKind.CRAFTING,
            month_stamp=dummy_avatar.world.month_stamp,
            start_text="州郡起事",
            result_text="众人退守城中",
            actors=[dummy_avatar],
            related_avatar_ids=[dummy_avatar.id],
            prompt="保留原始提示",
        )

    prompt = mock_tell.await_args.kwargs["prompt"]
    _assert_liuchao_context_present(prompt, context)
    assert "保留原始提示" in prompt


@pytest.mark.asyncio
async def test_no_scenario_prompts_do_not_contain_scenario_block(dummy_avatar):
    dummy_avatar.world.scripted_scenario = None

    with patch(
        "src.classes.long_term_objective.call_llm_with_task_name",
        new=AsyncMock(return_value={"long_term_objective": "守住道心"}),
    ) as objective_llm:
        await generate_long_term_objective(dummy_avatar)

    with patch(
        "src.classes.story_teller.call_llm_with_task_name",
        new=AsyncMock(return_value={"story": "短故事"}),
    ) as story_llm:
        await StoryTeller.tell_story("有人相遇", "各自离去", dummy_avatar)

    objective_infos = objective_llm.await_args.args[2]
    story_infos = story_llm.await_args.args[2]
    assert "Scenario narrative context:" not in objective_infos["world_lore"]
    assert "Scenario narrative context:" not in story_infos["story_prompt"]
