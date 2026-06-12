import pytest

from src.scenario.event_dispatcher import EventDispatcher
from src.scenario.event_handlers.main_event_handler import handle_main_event
from src.scenario.event_handlers.side_event_handler import handle_side_event
from src.scenario.scenario_loader import load


def build_liuchao_state(scenario, controlled_avatar="cheng-zongyang"):
    initial = scenario.scenario["initial_state"]
    avatars = {
        avatar["id"]: {
            "id": avatar["id"],
            "name": avatar["surname"] + avatar["given_name"],
            "realm": avatar["realm"],
            "alive": True,
            "skills": [],
            "stats": {},
            "items": [],
            "sect_id": avatar.get("sect_id"),
        }
        for avatar in initial["avatars"]
    }
    relations = {}
    for relation in initial.get("relationships", []):
        a, b = sorted([relation["a"], relation["b"]])
        relations[f"{a}:{b}"] = relation["value"]
    return {
        "realm_order": [
            "ZHU_JI",
            "NEI_SHI",
            "SHENG_XIANG",
            "RU_WEI",
            "ZUO_ZHAO",
            "TONG_YOU",
            "GUI_YUAN",
            "ZHI_ZHEN",
            "RU_SHEN",
        ],
        "player": avatars["cheng-zongyang"],
        "npcs": {key: value for key, value in avatars.items() if key != "cheng-zongyang"},
        "world": {
            "year": initial["year"],
            "month": initial["month"],
            "world_flags": dict(initial.get("world_flags", {})),
        },
        "controlled_avatar": controlled_avatar,
        "relations": relations,
        "scenario_runtime": {
            "scenario_id": scenario.scenario_id,
            "scenario_version": scenario.version,
            "controlled_avatar_id": controlled_avatar,
            "triggered_event_ids": [],
            "event_outcomes": {},
        },
    }


@pytest.mark.asyncio
async def test_liuchao_minimal_opening_dispatches_in_order():
    scenario = load("liuchao")
    state = build_liuchao_state(scenario)
    dispatcher = EventDispatcher(
        scenario.timeline,
        handlers={
            "main": handle_main_event,
            "side_event": handle_side_event,
        },
    )

    expected = [
        (1, "liuchao-opening", "liuchao_opening_seen"),
        (2, "duan-qiang-falls", "duan_qiang_fallen"),
        (3, "cheng-captured-by-qin", "cheng_captured_by_qin"),
        (4, "first-contact-taiyi", "cheng_met_taiyi"),
    ]
    for month, event_id, flag in expected:
        state["world"]["month"] = month
        triggered = await dispatcher.dispatch_month(state)
        assert [event["id"] for event in triggered] == [event_id]
        assert state["world"]["world_flags"][flag] is True

    assert state["relations"]["cheng-zongyang:wang-zhe"] == 60


def test_liuchao_initial_avatar_realms_follow_preset_order():
    scenario = load("liuchao")
    state = build_liuchao_state(scenario)

    known_realms = set(state["realm_order"])
    assert state["player"]["realm"] in known_realms
    assert all(npc["realm"] in known_realms for npc in state["npcs"].values())
