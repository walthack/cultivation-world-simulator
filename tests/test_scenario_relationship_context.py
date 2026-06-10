import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.classes.ai import llm_ai
from src.classes.long_term_objective import generate_long_term_objective
from src.classes.mutual_action.conversation import Conversation
from src.classes.relation.relation import NumericRelation, Relation, RelationState
from src.classes.relation.relationship_summary import build_relationship_summary
from src.scenario.state import ScriptedScenarioState


LIUCHAO_SCENARIO_PATH = Path("config/scenarios/liuchao/scenario.json")


def _make_related_avatar(name: str, avatar_id: str):
    avatar = MagicMock()
    avatar.name = name
    avatar.id = avatar_id
    avatar.is_dead = False
    avatar.birth_month_stamp = 0
    avatar.gender.value = "male"
    avatar.relations = {}
    avatar.computed_relations = {}
    avatar.get_info.return_value = {"name": name}
    avatar.get_planned_actions_str.return_value = ""
    return avatar


def _set_one_way_relation(avatar, other, *, friendliness: int, relation: Relation | None = None) -> None:
    avatar.relations[other] = RelationState(
        identity_relations={relation} if relation is not None else set(),
        friendliness=friendliness,
        last_numeric_relation=(
            NumericRelation.BEST_FRIEND if friendliness >= 70 else NumericRelation.ARCHENEMY
        ),
    )


def test_relationship_summary_is_callable_by_npc_id(dummy_avatar):
    ally = _make_related_avatar("王哲", "wang-zhe")
    enemy = _make_related_avatar("狼羽", "lang-yu")
    _set_one_way_relation(dummy_avatar, ally, friendliness=80, relation=Relation.IS_SWORN_SIBLING_OF)
    _set_one_way_relation(dummy_avatar, enemy, friendliness=-80)
    dummy_avatar.world.avatar_manager.register_avatar(dummy_avatar)

    summary = build_relationship_summary(dummy_avatar.world, dummy_avatar.id)

    assert "与王哲" in summary
    assert "高好感" in summary
    assert "与狼羽" in summary
    assert "敌对" in summary


@pytest.mark.asyncio
async def test_long_term_objective_prompt_contains_npc_relationship_summary(dummy_avatar):
    ally = _make_related_avatar("王哲", "wang-zhe")
    _set_one_way_relation(dummy_avatar, ally, friendliness=80, relation=Relation.IS_SWORN_SIBLING_OF)
    dummy_avatar.get_expanded_info = MagicMock(return_value={"name": dummy_avatar.name})

    with patch(
        "src.classes.long_term_objective.call_llm_with_task_name",
        new=AsyncMock(return_value={"long_term_objective": "与王哲共谋大业"}),
    ) as mock_llm:
        await generate_long_term_objective(dummy_avatar)

    avatar_info = mock_llm.await_args.args[2]["avatar_info"]
    assert "关系网摘要" in avatar_info
    assert "与王哲" in avatar_info["关系网摘要"]
    assert "高好感" in avatar_info["关系网摘要"]


def test_conversation_prompt_contains_relationship_and_liuchao_narrative_context(dummy_avatar):
    target = _make_related_avatar("王哲", "wang-zhe")
    _set_one_way_relation(dummy_avatar, target, friendliness=80, relation=Relation.IS_SWORN_SIBLING_OF)
    _set_one_way_relation(target, dummy_avatar, friendliness=75, relation=Relation.IS_SWORN_SIBLING_OF)
    dummy_avatar.get_expanded_info = MagicMock(return_value={"name": dummy_avatar.name})
    dummy_avatar.get_planned_actions_str = MagicMock(return_value="")

    profile = json.loads(LIUCHAO_SCENARIO_PATH.read_text(encoding="utf-8"))["initial_state"]["generation_profile"]
    dummy_avatar.world.scripted_scenario = ScriptedScenarioState(
        scenario_id="liuchao",
        timeline=[],
        generation_profile=profile,
    )
    dummy_avatar.world.set_world_lore("默认修仙世界观：太一山洞府中有金精之气。")

    infos = Conversation(dummy_avatar, dummy_avatar.world)._build_prompt_infos(target)
    prompt_payload = str(infos["avatar_infos"])

    assert "关系网摘要" in prompt_payload
    assert "与王哲" in prompt_payload
    assert "六朝并立于架空乱世" in prompt_payload
    assert "门阀" in prompt_payload
    assert "成长体系" in prompt_payload
    assert "六朝功业进身" in prompt_payload
    assert "官阶 [主要成长轴]" in prompt_payload
    assert "太一山洞府" not in prompt_payload
    assert "金精之气" not in prompt_payload


@pytest.mark.asyncio
async def test_action_decision_prompt_contains_npc_relationship_summary(dummy_avatar):
    enemy = _make_related_avatar("狼羽", "lang-yu")
    _set_one_way_relation(dummy_avatar, enemy, friendliness=-80)
    dummy_avatar.get_expanded_info = MagicMock(return_value={"name": dummy_avatar.name})
    dummy_avatar.world.get_observable_avatars = MagicMock(return_value=[enemy])
    payload = {
        dummy_avatar.name: {
            "action_name_params_pairs": [["MoveAwayFromAvatar", {"target_avatar": "狼羽"}]],
            "avatar_thinking": "避开敌手。",
            "current_emotion": "emotion_calm",
            "short_term_objective": "远离狼羽",
        }
    }

    with patch("src.classes.ai.call_llm_with_task_name", new=AsyncMock(return_value=payload)) as mock_llm, patch(
        "src.classes.ai.get_action_infos_str",
        return_value="MoveAwayFromAvatar",
    ), patch(
        "src.classes.core.avatar.info_presenter.get_avatar_ai_context",
        return_value={},
    ):
        await llm_ai._decide(dummy_avatar.world, [dummy_avatar])

    avatar_info = mock_llm.await_args.args[2]["avatar_info"]
    assert "关系网摘要" in avatar_info
    assert "与狼羽" in avatar_info["关系网摘要"]
    assert "敌对" in avatar_info["关系网摘要"]
    assert "成长体系" in avatar_info
    assert "修真境界（cultivation）" in avatar_info["成长体系"]


def test_conversation_no_scenario_no_relations_preserves_prompt_shape(dummy_avatar):
    target = _make_related_avatar("路人", "passerby")
    dummy_avatar.relations = {}
    dummy_avatar.computed_relations = {}
    dummy_avatar.get_expanded_info = MagicMock(return_value={"name": dummy_avatar.name})
    dummy_avatar.get_planned_actions_str = MagicMock(return_value="")
    dummy_avatar.world.scripted_scenario = None

    infos = Conversation(dummy_avatar, dummy_avatar.world)._build_prompt_infos(target)

    assert set(infos["avatar_infos"]) == {dummy_avatar.name, target.name}
    assert infos["avatar_infos"][dummy_avatar.name]["角色资料"] == {"name": dummy_avatar.name}
    assert "修真境界（cultivation）" in infos["avatar_infos"][dummy_avatar.name]["成长体系"]
    assert infos["avatar_infos"][target.name]["角色资料"] == {"name": target.name}
    assert "修真境界（cultivation）" in infos["avatar_infos"][target.name]["成长体系"]
