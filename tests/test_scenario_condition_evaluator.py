import random

import pytest

from src.scenario.condition_evaluator import ConditionEvaluationError, evaluate_condition


def state():
    return {
        "realm_order": ["LIAN_QI", "ZHU_JI", "JIE_DAN"],
        "player": {
            "id": "cheng-zongyang",
            "realm": "ZHU_JI",
            "sect_id": "taiyi",
            "skills": ["九阳神功"],
            "stats": {"yang_qi": 9},
        },
        "npcs": {
            "wang-zhe": {"id": "wang-zhe", "alive": True, "realm": "JIE_DAN"},
            "xiao-zi": {"id": "xiao-zi", "alive": True, "realm": "LIAN_QI"},
        },
        "world": {"year": 2, "month": 3, "world_flags": {"started": True}},
        "relations": {"cheng-zongyang:wang-zhe": 60, "wang-zhe:xiao-zi": 30},
        "scenario_runtime": {"triggered_event_ids": ["intro"]},
    }


def test_player_realm():
    assert evaluate_condition(state(), {"player_realm": {"realm": "LIAN_QI"}})


def test_player_sect():
    assert evaluate_condition(state(), {"player_sect": {"sect_id": "taiyi"}})


def test_player_has_skill():
    assert evaluate_condition(state(), {"player_has_skill": {"skill": "九阳神功"}})


def test_player_stat():
    assert evaluate_condition(state(), {"player_stat": {"stat": "yang_qi", "op": ">=", "value": 9}})


def test_player_relation():
    assert evaluate_condition(state(), {"player_relation": {"npc_id": "wang-zhe", "value": 50}})


def test_world_year():
    assert evaluate_condition(state(), {"world_year": {"value": 2}})


def test_world_month():
    assert evaluate_condition(state(), {"world_month": {"value": 3}})


def test_world_flag():
    assert evaluate_condition(state(), {"world_flag": {"flag": "started"}})


def test_npc_alive():
    assert evaluate_condition(state(), {"npc_alive": {"npc_id": "wang-zhe"}})


def test_npc_realm():
    assert evaluate_condition(state(), {"npc_realm": {"npc_id": "wang-zhe", "realm": "ZHU_JI"}})


def test_npc_relation():
    assert evaluate_condition(state(), {"npc_relation": {"a": "wang-zhe", "b": "xiao-zi", "value": 20}})


def test_random_chance():
    assert evaluate_condition(state(), {"random_chance": {"chance": 1.0}}, rng=random.Random(7))


def test_always():
    assert evaluate_condition(state(), {"always": {}})


def test_composition_all_any_not():
    expr = {
        "all": [
            {"world_year": {"value": 2}},
            {"any": [{"world_month": {"value": 4}}, {"world_month": {"value": 3}}]},
            {"not": {"world_flag": {"flag": "missing"}}},
        ]
    }
    assert evaluate_condition(state(), expr)


def test_unknown_predicate_raises():
    with pytest.raises(ConditionEvaluationError):
        evaluate_condition(state(), {"python_lambda": {"expr": "lambda: True"}})
