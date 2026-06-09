import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.classes.action.breakthrough import Breakthrough
from src.classes.action.move_to_avatar import MoveToAvatar
from src.classes.action.move_to_direction import MoveToDirection
from src.classes.action.respire import Respire
from src.classes.environment.region import CultivateRegion
from src.classes.essence import EssenceType
from src.classes.sect_decider import SectDecider, SectDecisionResult
from src.scenario.narrative_context import SCENARIO_NARRATIVE_INSTRUCTION
from src.scenario.state import ScriptedScenarioState
from src.sim.managers.sect_manager import SectManager, SectTerritorySnapshot


LIUCHAO_SCENARIO_PATH = Path("config/scenarios/liuchao/scenario.json")


def _attach_liuchao_scenario(world) -> dict:
    data = json.loads(LIUCHAO_SCENARIO_PATH.read_text(encoding="utf-8"))
    profile = data["initial_state"]["generation_profile"]
    world.scripted_scenario = ScriptedScenarioState(
        scenario_id="liuchao",
        timeline=[],
        generation_profile=profile,
    )
    return profile["narrative_context"]


def test_liuchao_annual_settlement_event_applies_term_map(base_world):
    _attach_liuchao_scenario(base_world)
    sect = MagicMock()
    sect.id = 1
    sect.name = "金丹宗门"
    sect.members = {}
    sect.magic_stone = 1000
    sect.war_weariness = 0
    sect.estimate_yearly_member_upkeep.return_value = (50, {})

    snapshot = SectTerritorySnapshot(
        active_sects=[sect],
        sect_centers={1: (0, 0)},
        tile_owners={(0, 0): [1]},
        owned_tiles_by_sect={1: [(0, 0)]},
        border_contact_counts={},
        border_tiles_by_sect={1: 0},
        boundary_edges_by_sect={1: []},
    )
    manager = SectManager(base_world)

    with patch.object(manager, "_compute_snapshot", return_value=snapshot), patch.object(
        manager,
        "calculate_income_by_sect",
        return_value={1: 100},
    ):
        events = manager.update_sects()

    assert len(events) == 1
    assert "还丹门阀/势力" in events[0].content
    assert "钱粮/资财" in events[0].content
    assert "灵石" not in events[0].content
    assert "宗门" not in events[0].content


@pytest.mark.asyncio
async def test_liuchao_breakthrough_and_movement_events_apply_term_map(dummy_avatar):
    _attach_liuchao_scenario(dummy_avatar.world)
    dummy_avatar.name = "金丹修士"

    breakthrough_event = Breakthrough(dummy_avatar, dummy_avatar.world).start()

    target = MagicMock()
    target.id = "target"
    target.name = "宗门洞府守卫"
    dummy_avatar.world.avatar_manager.avatars[target.id] = target
    movement_event = MoveToAvatar(dummy_avatar, dummy_avatar.world).start(target.id)
    movement_finish_event = (await MoveToDirection(dummy_avatar, dummy_avatar.world).finish("North"))[0]

    assert "还丹" in breakthrough_event.content
    assert "晋阶/进境品阶" in breakthrough_event.content
    assert "金丹" not in breakthrough_event.content
    assert "突破" not in breakthrough_event.content
    assert "门阀/势力福地守卫" in movement_event.content
    assert "宗门" not in movement_event.content
    assert "洞府" not in movement_event.content
    assert "还丹" in movement_finish_event.content
    assert "金丹" not in movement_finish_event.content


@pytest.mark.asyncio
async def test_liuchao_recruitment_event_applies_term_map(dummy_avatar):
    _attach_liuchao_scenario(dummy_avatar.world)
    dummy_avatar.name = "金丹散修"
    dummy_avatar.sect = None
    sect = MagicMock()
    sect.id = 1
    sect.name = "测试宗门"
    sect.magic_stone = 1000
    sect.accepts_avatar_race.return_value = True
    dummy_avatar.world.avatar_manager.avatars = {dummy_avatar.id: dummy_avatar}
    decision_context = MagicMock()
    decision_context.recruitment_candidates = [
        {
            "avatar_id": dummy_avatar.id,
            "alignment_recruitable": True,
            "race_recruitable": True,
        }
    ]
    result = SectDecisionResult()
    outcome = MagicMock(accepted=True, result_text="测试宗门以灵石招募金丹散修。")

    with patch(
        "src.classes.sect_decider.resolve_sect_recruitment",
        new=AsyncMock(return_value=outcome),
    ), patch.object(dummy_avatar, "join_sect"):
        await SectDecider._process_recruitment(
            sect=sect,
            decision_context=decision_context,
            world=dummy_avatar.world,
            recruit_cost=500,
            result=result,
            selected_ids={dummy_avatar.id},
        )

    assert len(result.events) == 2
    assert all("钱粮/资财" in event.content for event in result.events)
    assert all("门阀/势力" in event.content for event in result.events)
    assert all("还丹" in event.content for event in result.events)
    assert all("灵石" not in event.content for event in result.events)


def test_liuchao_cultivation_event_applies_term_map(dummy_avatar):
    _attach_liuchao_scenario(dummy_avatar.world)
    dummy_avatar.name = "金丹修士"
    dummy_avatar.tile.region = CultivateRegion(
        id=901,
        name="宗门洞府",
        desc="测试修炼地",
        essence_type=EssenceType.GOLD,
        essence_density=5,
    )

    event = Respire(dummy_avatar, dummy_avatar.world).start()

    assert "还丹" in event.content
    assert "门阀/势力福地" in event.content
    assert "金丹" not in event.content
    assert "宗门" not in event.content
    assert "洞府" not in event.content


def test_no_scenario_mechanical_event_does_not_apply_term_map(dummy_avatar):
    dummy_avatar.world.scripted_scenario = None
    dummy_avatar.name = "金丹修士"

    event = Breakthrough(dummy_avatar, dummy_avatar.world).start()

    assert "金丹修士" in event.content
    assert "突破境界" in event.content
    assert "还丹" not in event.content
    assert "晋阶/进境" not in event.content


@pytest.mark.asyncio
async def test_liuchao_sect_decider_prompt_contains_scenario_context(base_world):
    context = _attach_liuchao_scenario(base_world)
    base_world.set_world_lore("默认修仙世界观：宗门以灵石争夺秘境。")
    sect = MagicMock(name="sect")
    sect.id = 1
    sect.name = "测试宗门"
    decision_context = MagicMock()
    for field in (
        "basic_structured",
        "identity",
        "power",
        "territory",
        "self_assessment",
        "economy",
        "rule",
        "history",
    ):
        setattr(decision_context, field, {})
    decision_context.basic_text = ""
    decision_context.diplomacy_targets = []
    decision_context.active_wars = []
    decision_context.recruitment_candidates = []
    decision_context.member_candidates = []
    decision_context.relations = []
    decision_context.relations_summary = ""

    with patch.object(SectDecider, "_llm_available", return_value=True), patch(
        "src.classes.sect_decider.call_llm_with_task_name",
        new=AsyncMock(return_value={"thinking": "观望时局"}),
    ) as mock_llm:
        await SectDecider._plan(
            sect,
            decision_context,
            base_world,
            recruit_cost=500,
            support_amount=300,
        )

    world_lore = mock_llm.await_args.kwargs["infos"]["world_lore"]
    assert world_lore.startswith(SCENARIO_NARRATIVE_INSTRUCTION)
    assert context["background"] in world_lore
    assert "六朝并立于架空乱世" in world_lore
    assert "门阀/势力" in world_lore
    assert "默认修仙世界观" not in world_lore
