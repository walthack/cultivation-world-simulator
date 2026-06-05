import pytest

from src.scenario.event_handlers.character_introduction_handler import handle_character_introduction
from src.scenario.event_handlers.ending_handler import handle_ending
from src.scenario.event_handlers.main_event_handler import handle_main_event
from src.scenario.event_handlers.relation_change_handler import handle_relation_change
from src.scenario.event_handlers.side_event_handler import handle_side_event
from src.scenario.event_handlers.world_event_handler import handle_world_event


def state():
    return {
        "player": {"id": "cheng-zongyang", "skills": [], "stats": {}, "items": []},
        "npcs": {"wang-zhe": {"id": "wang-zhe", "alive": True, "joined": False}},
        "world": {"world_flags": {}},
        "relations": {"cheng-zongyang:wang-zhe": 50},
        "scenario_runtime": {},
    }


@pytest.mark.asyncio
async def test_main_event_handler_uses_default_outcome_choice():
    s = state()
    event = {
        "id": "main",
        "type": "main",
        "description": "choose",
        "default_outcome": "accept",
        "choices": [
            {"id": "accept", "effects": [{"type": "gain_skill", "skill": "九阳神功"}]},
            {"id": "decline", "effects": [{"type": "set_flag", "flag": "declined"}]},
        ],
    }
    outcome = await handle_main_event(s, event)
    assert outcome.choice_id == "accept"
    assert s["player"]["skills"] == ["九阳神功"]


@pytest.mark.asyncio
async def test_character_introduction_handler_spawns_npc():
    s = state()
    await handle_character_introduction(s, {"id": "intro", "spawn_avatar": {"id": "xiao-zi", "alive": True}})
    assert s["npcs"]["xiao-zi"]["alive"] is True


@pytest.mark.asyncio
async def test_relation_change_handler_applies_relation_delta():
    s = state()
    await handle_relation_change(
        s,
        {"id": "rel", "a": "cheng-zongyang", "b": "wang-zhe", "delta": 10},
    )
    assert s["relations"]["cheng-zongyang:wang-zhe"] == 60


@pytest.mark.asyncio
async def test_world_event_handler_applies_effects():
    s = state()
    await handle_world_event(s, {"id": "world", "effects": [{"type": "set_flag", "flag": "storm"}]})
    assert s["world"]["world_flags"]["storm"] is True


@pytest.mark.asyncio
async def test_side_event_handler_applies_effects():
    s = state()
    await handle_side_event(s, {"id": "side", "effects": [{"type": "gain_item", "item": "线索"}]})
    assert s["player"]["items"] == ["线索"]


@pytest.mark.asyncio
async def test_ending_handler_sets_runtime_ending():
    s = state()
    await handle_ending(s, {"id": "ending", "outcome_text": "终局"})
    assert s["scenario_runtime"]["ending"]["outcome_text"] == "终局"
