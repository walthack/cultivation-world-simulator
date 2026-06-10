from __future__ import annotations

from src.scenario.injector import inject_scenario_into_world
from src.scenario.progression_metrics import build_progression_metrics
from src.scenario.progression_profile import build_progression_context
from src.scenario.scenario_loader import load as load_scenario
from src.scenario.state import ScriptedScenarioState


def _load_progression_context(base_world, scenario_id: str) -> str:
    inject_scenario_into_world(base_world, load_scenario(scenario_id))
    return build_progression_context(base_world)


def test_liuchao_progression_prompt_uses_scenario_profile(base_world):
    context = _load_progression_context(base_world, "liuchao")

    assert "六朝功业进身" in context
    assert "功业 [主要成长轴]" in context
    assert "立身 → 建功 → 柱石 → 定鼎" in context
    assert "官阶 [主要成长轴]" in context
    assert "名望 [主要成长轴]" in context
    assert "优先围绕晋升官阶、积累功业" in context
    assert "成长体系：修真境界（cultivation）" not in context


def test_sanguo_progression_prompt_uses_scenario_profile(base_world):
    context = _load_progression_context(base_world, "sanguo")

    assert "三国功业进身" in context
    assert "军功 [主要成长轴]" in context
    assert "官职 [主要成长轴]" in context
    assert "声望 [主要成长轴]" in context
    assert "从军 → 破阵 → 镇军 → 定鼎" in context
    assert "目标与行动应优先围绕建立军功" in context
    assert "成长体系：修真境界（cultivation）" not in context


def test_missing_progression_profile_uses_default_context_unchanged(base_world):
    base_world.scripted_scenario = ScriptedScenarioState(
        scenario_id="legacy",
        timeline=[],
        generation_profile={"narrative_context": {"background": "legacy"}},
    )

    context = build_progression_context(base_world)

    assert context == (
        "成长体系：修真境界（cultivation）\n"
        "目标指引：长期目标可围绕修炼积累、突破境界与仙途发展，并结合角色身份和处境。\n"
        "- 修真境界 [主要成长轴]：以修为积累和境界突破衡量个人成长。；层级：练气 → 筑基 → 金丹 → 元婴"
    )


def test_malformed_progression_profile_falls_back_without_raising(base_world, caplog):
    base_world.scripted_scenario = ScriptedScenarioState(
        scenario_id="malformed",
        timeline=[],
        generation_profile={"progression_profile": {"id": "broken", "label": "Broken"}},
    )

    context = build_progression_context(base_world)

    assert "成长体系：修真境界（cultivation）" in context
    assert "malformed progression_profile" in caplog.text


def test_progression_metrics_are_namespaced_and_separate_from_term_ratios(base_world):
    _load_progression_context(base_world, "sanguo")

    metrics = build_progression_metrics(
        base_world,
        "以军功晋升镇军，不求突破金丹。",
        goal_text="以军功晋升镇军",
        behavior_text="整军破阵，积累军功",
    )

    assert metrics["progression.profile_selected_count"] == 1
    assert metrics["progression.axis_mentions.military_merit"] == 2
    assert metrics["progression.default_residual_count"] == 1
    assert metrics["progression.default_residual_rate"] == 1.0
    assert metrics["progression.goal_behavior_consistent"] is False
    assert not any(key.startswith("term_ratio") for key in metrics)
