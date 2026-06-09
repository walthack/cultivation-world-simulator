from unittest.mock import AsyncMock, patch

import pytest

from src.classes.age import Age
from src.classes.alignment import Alignment
from src.classes.core.avatar import Avatar, Gender
from src.classes.environment.region import CityRegion
from src.classes.event import Event
from src.classes.root import Root
from src.scenario.state import ScriptedScenarioState
from src.sim.simulator import Simulator
from src.sim.simulator_engine.context import SimulationStepContext
from src.sim.simulator_engine.phases import social
from src.systems.cultivation import Realm
from src.systems.time import Month, Year, create_month_stamp


def _make_avatar(world, *, avatar_id: str, name: str, x: int) -> Avatar:
    avatar = Avatar(
        world=world,
        name=name,
        id=avatar_id,
        birth_month_stamp=create_month_stamp(Year(1), Month.JANUARY),
        age=Age(20, Realm.Qi_Refinement),
        gender=Gender.MALE,
        pos_x=x,
        pos_y=0,
        root=Root.GOLD,
        personas=[],
        alignment=Alignment.NEUTRAL,
    )
    avatar.personas = []
    avatar.technique = None
    avatar.recalc_effects()
    world.avatar_manager.register_avatar(avatar)
    return avatar


def _put_in_region(world, avatars: list[Avatar]) -> None:
    region = CityRegion(id=9001, name="Social City", desc="Test city")
    world.map.regions[region.id] = region
    for avatar in avatars:
        avatar.tile = world.map.get_tile(avatar.pos_x, avatar.pos_y)
        avatar.tile.region = region


def _enable_social_scenario(world, *, probability: float = 1.0, maximum: int = 1) -> None:
    world.scripted_scenario = ScriptedScenarioState(
        scenario_id="social-test",
        timeline=[],
        generation_profile={
            "social_simulation": {
                "conversation_probability": probability,
                "max_conversations_per_month": maximum,
            }
        },
    )


@pytest.mark.asyncio
async def test_automatic_social_phase_matches_same_region_npcs(base_world):
    avatar_a = _make_avatar(base_world, avatar_id="social-a", name="Social A", x=0)
    avatar_b = _make_avatar(base_world, avatar_id="social-b", name="Social B", x=1)
    _put_in_region(base_world, [avatar_a, avatar_b])
    _enable_social_scenario(base_world)
    ctx = SimulationStepContext.create(base_world)
    conversation_event = Event(base_world.month_stamp, "automatic conversation")

    with patch.object(social.random, "shuffle", side_effect=lambda pairs: None), patch.object(
        social.random, "random", return_value=0.0
    ), patch.object(
        social,
        "_run_automatic_conversation",
        new=AsyncMock(return_value=[conversation_event]),
    ) as run_conversation:
        events = await social.phase_automatic_social(base_world, ctx)

    assert events == [conversation_event]
    run_conversation.assert_awaited_once_with(base_world, avatar_a, avatar_b)


@pytest.mark.asyncio
async def test_automatic_conversation_updates_relationship_via_delta_service(base_world):
    avatar_a = _make_avatar(base_world, avatar_id="relation-a", name="Relation A", x=0)
    avatar_b = _make_avatar(base_world, avatar_id="relation-b", name="Relation B", x=1)
    _put_in_region(base_world, [avatar_a, avatar_b])
    _enable_social_scenario(base_world)
    ctx = SimulationStepContext.create(base_world)

    llm_result = {
        avatar_b.name: {
            "thinking": "The conversation went well.",
            "conversation_content": "They agreed to cooperate.",
        }
    }
    with patch.object(social.random, "shuffle", side_effect=lambda pairs: None), patch.object(
        social.random, "random", return_value=0.0
    ), patch(
        "src.classes.mutual_action.mutual_action.call_llm_with_task_name",
        new=AsyncMock(return_value=llm_result),
    ), patch(
        "src.classes.mutual_action.conversation.RelationDeltaService.resolve_event_text_delta",
        new=AsyncMock(return_value=(2, 3)),
    ) as resolve_delta, patch(
        "src.classes.mutual_action.conversation.StoryEventService.maybe_create_story",
        new=AsyncMock(return_value=None),
    ):
        events = await social.phase_automatic_social(base_world, ctx)

    assert any("They agreed to cooperate." in event.content for event in events)
    assert avatar_a.get_friendliness(avatar_b) == 2
    assert avatar_b.get_friendliness(avatar_a) == 3
    resolve_delta.assert_awaited_once()


@pytest.mark.asyncio
async def test_automatic_social_phase_is_unreachable_without_scenario(base_world):
    avatar_a = _make_avatar(base_world, avatar_id="sandbox-a", name="Sandbox A", x=0)
    avatar_b = _make_avatar(base_world, avatar_id="sandbox-b", name="Sandbox B", x=1)
    _put_in_region(base_world, [avatar_a, avatar_b])
    ctx = SimulationStepContext.create(base_world)

    with patch.object(social, "_run_automatic_conversation", new=AsyncMock()) as run_conversation:
        events = await social.phase_automatic_social(base_world, ctx)

    assert events == []
    run_conversation.assert_not_awaited()


@pytest.mark.asyncio
async def test_automatic_social_phase_honors_probability_and_monthly_limit(base_world):
    avatars = [
        _make_avatar(base_world, avatar_id=f"limited-{index}", name=f"Limited {index}", x=index)
        for index in range(4)
    ]
    _put_in_region(base_world, avatars)
    ctx = SimulationStepContext.create(base_world)

    _enable_social_scenario(base_world, probability=0.0, maximum=2)
    with patch.object(social, "_run_automatic_conversation", new=AsyncMock()) as run_conversation:
        assert await social.phase_automatic_social(base_world, ctx) == []
        run_conversation.assert_not_awaited()

    _enable_social_scenario(base_world, probability=1.0, maximum=1)
    with patch.object(social.random, "shuffle", side_effect=lambda pairs: None), patch.object(
        social.random, "random", return_value=0.0
    ), patch.object(
        social,
        "_run_automatic_conversation",
        new=AsyncMock(return_value=[]),
    ) as run_conversation:
        await social.phase_automatic_social(base_world, ctx)

    assert run_conversation.await_count == 1


@pytest.mark.asyncio
async def test_simulator_collects_automatic_social_phase_events(base_world):
    _enable_social_scenario(base_world)
    sim = Simulator(base_world)
    social_event = Event(base_world.month_stamp, "social phase event")

    with patch.object(
        social,
        "phase_automatic_social",
        new=AsyncMock(return_value=[social_event]),
    ) as automatic_social:
        events = await sim.step()

    automatic_social.assert_awaited_once()
    assert any(event.id == social_event.id for event in events)
