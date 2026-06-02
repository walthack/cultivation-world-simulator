import logging

import pytest

from src.scenario.effect_applier import EffectError, apply_effects
from src.scenario.scenario_loader import MissingReferenceError


def state():
    return {
        "player": {
            "id": "cheng-zongyang",
            "skills": [],
            "stats": {"yang_qi": 0},
            "items": [],
        },
        "npcs": {
            "wang-zhe": {
                "id": "wang-zhe",
                "alive": True,
                "joined": False,
                "realm": "ZHU_JI",
            }
        },
        "world": {"world_flags": {}},
        "relations": {},
        "scenario_runtime": {"triggered_event_ids": []},
    }


def test_gain_skill():
    s = state()
    apply_effects(s, [{"type": "gain_skill", "skill": "九阳神功"}])
    assert s["player"]["skills"] == ["九阳神功"]


def test_lose_skill():
    s = state()
    s["player"]["skills"] = ["九阳神功"]
    apply_effects(s, [{"type": "lose_skill", "skill": "九阳神功"}])
    assert s["player"]["skills"] == []


def test_gain_stat():
    s = state()
    apply_effects(s, [{"type": "gain_stat", "stat": "yang_qi", "amount": 9}])
    assert s["player"]["stats"]["yang_qi"] == 9


def test_lose_stat():
    s = state()
    s["player"]["stats"]["yang_qi"] = 9
    apply_effects(s, [{"type": "lose_stat", "stat": "yang_qi", "amount": 4}])
    assert s["player"]["stats"]["yang_qi"] == 5


def test_set_stat():
    s = state()
    apply_effects(s, [{"type": "set_stat", "stat": "yang_qi", "value": 12}])
    assert s["player"]["stats"]["yang_qi"] == 12


def test_gain_item():
    s = state()
    apply_effects(s, [{"type": "gain_item", "item": "九阳秘卷"}])
    assert s["player"]["items"] == ["九阳秘卷"]


def test_lose_item():
    s = state()
    s["player"]["items"] = ["九阳秘卷"]
    apply_effects(s, [{"type": "lose_item", "item": "九阳秘卷"}])
    assert s["player"]["items"] == []


def test_set_flag():
    s = state()
    apply_effects(s, [{"type": "set_flag", "flag": "cheng_received_jiuyang"}])
    assert s["world"]["world_flags"]["cheng_received_jiuyang"] is True


def test_clear_flag():
    s = state()
    s["world"]["world_flags"]["cheng_received_jiuyang"] = True
    apply_effects(s, [{"type": "clear_flag", "flag": "cheng_received_jiuyang"}])
    assert "cheng_received_jiuyang" not in s["world"]["world_flags"]


def test_npc_join():
    s = state()
    apply_effects(s, [{"type": "npc_join", "npc_id": "wang-zhe"}])
    assert s["npcs"]["wang-zhe"]["joined"] is True


def test_npc_leave():
    s = state()
    s["npcs"]["wang-zhe"]["joined"] = True
    apply_effects(s, [{"type": "npc_leave", "npc_id": "wang-zhe"}])
    assert s["npcs"]["wang-zhe"]["joined"] is False


def test_npc_die():
    s = state()
    apply_effects(s, [{"type": "npc_die", "npc_id": "wang-zhe"}])
    assert s["npcs"]["wang-zhe"]["alive"] is False


def test_npc_set_realm():
    s = state()
    apply_effects(s, [{"type": "npc_set_realm", "npc_id": "wang-zhe", "realm": "YUAN_YING"}])
    assert s["npcs"]["wang-zhe"]["realm"] == "YUAN_YING"


def test_npc_set_relation():
    s = state()
    apply_effects(s, [{"type": "npc_set_relation", "a": "cheng-zongyang", "b": "wang-zhe", "value": 80}])
    assert s["relations"]["cheng-zongyang:wang-zhe"] == 80


def test_relation_change():
    s = state()
    s["relations"]["cheng-zongyang:wang-zhe"] = 50
    apply_effects(s, [{"type": "relation_change", "a": "cheng-zongyang", "b": "wang-zhe", "delta": 20}])
    assert s["relations"]["cheng-zongyang:wang-zhe"] == 70


def test_world_event_trigger():
    s = state()
    apply_effects(s, [{"type": "world_event_trigger", "event_id": "intro"}])
    assert s["scenario_runtime"]["triggered_event_ids"] == ["intro"]


def test_economy_event_noop(caplog):
    s = state()
    with caplog.at_level(logging.INFO):
        apply_effects(s, [{"type": "economy_event", "kind": "market"}])
    assert "Scenario economy_event no-op" in caplog.text


def test_missing_npc_reference_raises_and_rolls_back():
    s = state()
    with pytest.raises(MissingReferenceError):
        apply_effects(
            s,
            [
                {"type": "gain_skill", "skill": "九阳神功"},
                {"type": "npc_die", "npc_id": "missing"},
            ],
        )
    assert s["player"]["skills"] == []


def test_unknown_effect_raises():
    with pytest.raises(EffectError):
        apply_effects(state(), [{"type": "unknown"}])
