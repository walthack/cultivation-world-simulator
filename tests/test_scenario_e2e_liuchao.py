import pytest

from src.config.presets import get_preset_regions
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("controlled_avatar", "expected_event_id", "expected_choice_id"),
    [
        ("cheng-zongyang", "cheng-zongyang-arrives-at-linan-gate", "observe"),
        ("wang-zhe", "wang-zhe-arrives-at-linan-gate", "measure"),
        ("xiao-zi", "xiao-zi-arrives-at-linan-gate", "watch"),
    ],
)
async def test_liuchao_linan_gate_dispatches_only_matching_controlled_avatar(
    controlled_avatar,
    expected_event_id,
    expected_choice_id,
):
    scenario = load("liuchao")
    state = build_liuchao_state(scenario, controlled_avatar)
    dispatcher = EventDispatcher(
        scenario.timeline,
        handlers={
            "main": handle_main_event,
            "side_event": handle_side_event,
        },
    )

    state["world"]["year"] = 1
    state["world"]["month"] = 2
    triggered = await dispatcher.dispatch_month(state)

    assert [event["id"] for event in triggered] == [expected_event_id]
    assert state["world"]["world_flags"][f"linan_gate_seen_by_{controlled_avatar}"] is True
    assert state["scenario_runtime"]["event_outcomes"][expected_event_id]["choice_id"] == expected_choice_id


@pytest.mark.asyncio
async def test_liuchao_linan_gate_substitutes_controlled_avatar_in_effect_text():
    scenario = load("liuchao")
    state = build_liuchao_state(scenario, "xiao-zi")
    dispatcher = EventDispatcher(
        scenario.timeline,
        handlers={
            "main": handle_main_event,
            "side_event": handle_side_event,
        },
    )

    state["world"]["year"] = 1
    state["world"]["month"] = 2
    triggered = await dispatcher.dispatch_month(state)

    assert [event["id"] for event in triggered] == ["xiao-zi-arrives-at-linan-gate"]
    assert state["world"]["world_flags"]["linan_gate_seen_by_xiao-zi"] is True
    assert "linan_gate_seen_by_{controlled_avatar}" not in state["world"]["world_flags"]


def test_liuchao_stage_2c_dynasty_timeline_has_known_region_anchors():
    scenario = load("liuchao")
    region_ids = {region["id"] for region in get_preset_regions("liuchao")}
    expected = {
        "qin": {"qin-guanzhong-muster", "qin-changan-law-revision"},
        "han": {"han-luoyang-edict", "han-north-border-watchfires"},
        "jin": {"jin-jiankang-clan-council"},
        "song": {"song-linan-river-tax", "wang-zhe-passes-jiuyang"},
    }

    by_dynasty = {}
    for event in scenario.timeline:
        dynasty_id = event.get("dynasty_id")
        if dynasty_id is None:
            continue
        by_dynasty.setdefault(dynasty_id, set()).add(event["id"])
        assert event.get("trigger", {}).get("at_region_id") in region_ids

    for dynasty_id, event_ids in expected.items():
        assert event_ids <= by_dynasty.get(dynasty_id, set())
