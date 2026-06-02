import pytest

from src.scenario.event_dispatcher import EventDispatcher
from src.scenario.event_handlers.main_event_handler import handle_main_event
from src.scenario.event_handlers.side_event_handler import handle_side_event
from src.scenario.scenario_loader import load


def build_liuchao_state(scenario):
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
            "LIAN_QI",
            "ZHU_JI",
            "JIE_DAN",
            "YUAN_YING",
            "HUA_SHEN",
            "LIAN_XU",
            "HE_Ti",
            "DU_JIE",
            "DA_CHENG",
        ],
        "player": avatars["cheng-zongyang"],
        "npcs": {key: value for key, value in avatars.items() if key != "cheng-zongyang"},
        "world": {
            "year": initial["year"],
            "month": initial["month"],
            "world_flags": dict(initial.get("world_flags", {})),
        },
        "relations": relations,
        "scenario_runtime": {
            "scenario_id": scenario.scenario_id,
            "scenario_version": scenario.version,
            "controlled_avatar_id": "cheng-zongyang",
            "triggered_event_ids": [],
            "event_outcomes": {},
        },
    }


@pytest.mark.asyncio
async def test_liuchao_wang_zhe_passes_jiuyang_e2e():
    scenario = load("liuchao")
    state = build_liuchao_state(scenario)
    dispatcher = EventDispatcher(
        scenario.timeline,
        handlers={
            "main": handle_main_event,
            "side_event": handle_side_event,
        },
    )

    state["world"]["year"] = 1
    state["world"]["month"] = 1
    first = await dispatcher.dispatch_month(state)
    assert [event["id"] for event in first] == ["liuchao-opening"]

    state["world"]["year"] = 2
    state["world"]["month"] = 3
    triggered = await dispatcher.dispatch_month(state)

    assert [event["id"] for event in triggered] == ["wang-zhe-passes-jiuyang"]
    assert "九阳神功" in state["player"]["skills"]
    assert state["player"]["stats"]["yang_qi"] == 9
    assert state["world"]["world_flags"]["cheng_received_jiuyang"] is True
    assert state["relations"]["cheng-zongyang:wang-zhe"] == 70
    assert state["scenario_runtime"]["event_outcomes"]["wang-zhe-passes-jiuyang"]["choice_id"] == "accept"
