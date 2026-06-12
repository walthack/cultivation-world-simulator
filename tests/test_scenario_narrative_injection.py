import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.classes.long_term_objective import generate_long_term_objective
from src.classes.story_event_service import StoryEventKind, StoryEventService
from src.classes.story_teller import StoryTeller
from src.scenario.narrative_context import (
    SCENARIO_NARRATIVE_INSTRUCTION,
    build_prompt_world_lore,
    build_scenario_context_block,
)
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
    assert "太乙真宗" in text
    assert "九境" in text


def _assert_liuchao_m2_world_lore(text: str, context: dict) -> None:
    assert text.startswith(SCENARIO_NARRATIVE_INSTRUCTION)
    assert "秦军仍在草原与半兽人作战" in text
    assert "太乙真宗" in text
    assert "九境" in text
    assert "默认修仙世界观" not in text


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


def test_term_map_applies_to_injected_prompt_text_only(base_world):
    source_terms = "灵石 宗门 突破 修为 境界 炼丹 灵气 秘境 丹药 功法"
    replacements = "钱粮/资财 门阀/势力 晋阶/进境 功业 品阶 炼药/制剂 气运/地气 禁地/险境 药石 心法/武艺"
    base_world.scripted_scenario = ScriptedScenarioState(
        scenario_id="term_map",
        timeline=[],
        generation_profile={
            "term_map": dict(zip(source_terms.split(), replacements.split(), strict=True)),
            "narrative_context": {
                "world_lore_mode": "replace",
                "world_lore": source_terms,
            },
        },
    )

    prompt_lore = build_prompt_world_lore("默认世界观保留灵石原词", base_world)

    assert replacements in prompt_lore
    assert "默认世界观" not in prompt_lore


@pytest.mark.asyncio
async def test_liuchao_long_term_objective_prompt_contains_narrative_context(dummy_avatar):
    context = _attach_liuchao_scenario(dummy_avatar.world)
    dummy_avatar.world.set_world_lore("默认修仙世界观：宗门以灵石争夺秘境。")

    with patch(
        "src.classes.long_term_objective.call_llm_with_task_name",
        new=AsyncMock(return_value={"long_term_objective": "入仕建功"}),
    ) as mock_llm:
        await generate_long_term_objective(dummy_avatar)

    infos = mock_llm.await_args.args[2]
    _assert_liuchao_m2_world_lore(infos["world_lore"], context)
    progression = infos["avatar_info"]["成长体系"]
    assert "六朝生存、修行与立业" in progression
    assert "身份与官职 [主要成长轴]" in progression
    assert "名望与势力 [主要成长轴]" in progression
    assert "太乙九境 [主要成长轴]" in progression
    assert "汉国鸿胪寺大行令" in progression
    assert "同时尊重太乙九境" in progression


@pytest.mark.asyncio
async def test_liuchao_story_teller_prompt_contains_narrative_context(dummy_avatar):
    context = _attach_liuchao_scenario(dummy_avatar.world)
    dummy_avatar.world.set_world_lore("默认修仙世界观：宗门以灵石争夺秘境。")

    with patch(
        "src.classes.story_teller.call_llm_with_task_name",
        new=AsyncMock(return_value={"story": "短故事"}),
    ) as mock_llm:
        await StoryTeller.tell_story("州郡起事", "众人退守城中", dummy_avatar, prompt="保留原始提示")

    infos = mock_llm.await_args.args[2]
    _assert_liuchao_m2_world_lore(infos["world_lore"], context)
    assert infos["story_prompt"].startswith(SCENARIO_NARRATIVE_INSTRUCTION)
    assert "门阀" in infos["story_prompt"]
    assert "九境" in infos["story_prompt"]
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
    dummy_avatar.world.set_world_lore("原始世界观")

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
    assert objective_infos["world_lore"] == "原始世界观"
    assert story_infos["world_lore"] == "原始世界观"
    assert "Scenario narrative context:" not in objective_infos["world_lore"]
    assert "Scenario narrative context:" not in story_infos["story_prompt"]
    progression = objective_infos["avatar_info"]["成长体系"]
    assert "修真境界（cultivation）" in progression
    assert "练气 → 筑基 → 金丹 → 元婴" in progression
    assert "可选共存轴" not in progression


@pytest.mark.asyncio
async def test_scenario_without_progression_profile_uses_default_cultivation(dummy_avatar):
    dummy_avatar.world.scripted_scenario = ScriptedScenarioState(
        scenario_id="legacy_scenario",
        timeline=[],
        generation_profile={"narrative_context": {"background": "Legacy scenario"}},
    )

    with patch(
        "src.classes.long_term_objective.call_llm_with_task_name",
        new=AsyncMock(return_value={"long_term_objective": "突破金丹"}),
    ) as mock_llm:
        await generate_long_term_objective(dummy_avatar)

    progression = mock_llm.await_args.args[2]["avatar_info"]["成长体系"]
    assert "修真境界（cultivation）" in progression
    assert "金丹" in progression


@pytest.mark.asyncio
async def test_default_append_mode_preserves_v13_prompt_shape(dummy_avatar):
    context = {
        "background": "旧版背景",
        "style": "旧版风格",
        "terminology": "旧版术语",
    }
    dummy_avatar.world.scripted_scenario = ScriptedScenarioState(
        scenario_id="append_default",
        timeline=[],
        generation_profile={"narrative_context": context},
    )
    dummy_avatar.world.set_world_lore("原始世界观")

    with patch(
        "src.classes.long_term_objective.call_llm_with_task_name",
        new=AsyncMock(return_value={"long_term_objective": "守住道心"}),
    ) as mock_llm:
        await generate_long_term_objective(dummy_avatar)

    expected_block = (
        "Scenario narrative context:\n"
        "- Background: 旧版背景\n"
        "- Style: 旧版风格\n"
        "- Terminology: 旧版术语"
    )
    assert mock_llm.await_args.args[2]["world_lore"] == f"原始世界观\n\n{expected_block}"
