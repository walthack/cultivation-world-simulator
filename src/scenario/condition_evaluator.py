from __future__ import annotations

import random
from typing import Any

from .schema_constants import CANONICAL_PREDICATES
from .state_access import (
    as_id,
    get_npc,
    get_player,
    get_relation,
    get_scenario_runtime,
    get_value,
    get_world,
    get_world_flags,
)


class ConditionEvaluationError(ValueError):
    def __init__(self, expression: Any, reason: str):
        self.expression = expression
        self.reason = reason
        super().__init__(f"Condition evaluation failed: {reason}; expression={expression!r}")


def _require(params: dict[str, Any], key: str, expression: Any) -> Any:
    if key not in params:
        raise ConditionEvaluationError(expression, f"missing parameter: {key}")
    return params[key]


def _compare(actual: Any, expected: Any, op: str = "==") -> bool:
    if op == "==":
        return actual == expected
    if op == "!=":
        return actual != expected
    if op == ">=":
        return float(actual) >= float(expected)
    if op == ">":
        return float(actual) > float(expected)
    if op == "<=":
        return float(actual) <= float(expected)
    if op == "<":
        return float(actual) < float(expected)
    raise ValueError(f"unsupported op: {op}")


def _realm_rank(state: Any, realm: Any) -> int:
    order = get_value(state, "realm_order", None) or [
        "QI_REFINEMENT",
        "FOUNDATION_ESTABLISHMENT",
        "CORE_FORMATION",
        "NASCENT_SOUL",
        "SPIRIT_SEVERING",
        "DAO_INTEGRATION",
        "TRIBULATION",
        "MAHAYANA",
        "TRANSCENDENCE",
    ]
    normalized = str(realm or "").upper()
    try:
        return [str(item).upper() for item in order].index(normalized)
    except ValueError as exc:
        raise ConditionEvaluationError({"realm": realm}, f"unknown realm: {realm}") from exc


def _entity_realm_at_least(state: Any, entity: Any, realm: Any) -> bool:
    if entity is None:
        return False
    return _realm_rank(state, get_value(entity, "realm")) >= _realm_rank(state, realm)


def _eval_atomic(state: Any, predicate: str, params: Any, expression: Any, *, rng: random.Random | None) -> bool:
    params = params or {}
    if not isinstance(params, dict):
        raise ConditionEvaluationError(expression, "predicate parameters must be an object")

    player = get_player(state)
    world = get_world(state)

    if predicate == "always":
        return bool(params.get("value", True))
    if predicate == "controlled_avatar_is":
        return get_value(state, "controlled_avatar") == _require(params, "target_id", expression)
    if predicate == "player_realm":
        return _entity_realm_at_least(state, player, _require(params, "realm", expression))
    if predicate == "player_sect":
        return get_value(player, "sect_id") == _require(params, "sect_id", expression)
    if predicate == "player_has_skill":
        return _require(params, "skill", expression) in (get_value(player, "skills", []) or [])
    if predicate == "player_stat":
        stat = _require(params, "stat", expression)
        value = _require(params, "value", expression)
        op = str(params.get("op", ">="))
        return _compare(get_value(player, "stats", {}).get(stat, 0), value, op)
    if predicate == "player_relation":
        npc_id = _require(params, "npc_id", expression)
        value = _require(params, "value", expression)
        op = str(params.get("op", ">="))
        return _compare(get_relation(state, get_value(player, "id"), npc_id), value, op)
    if predicate == "world_year":
        return _compare(get_value(world, "year", 0), _require(params, "value", expression), str(params.get("op", "==")))
    if predicate == "world_month":
        return _compare(get_value(world, "month", 0), _require(params, "value", expression), str(params.get("op", "==")))
    if predicate == "world_flag":
        return bool(get_world_flags(state).get(str(_require(params, "flag", expression)))) is bool(params.get("value", True))
    if predicate == "npc_alive":
        npc = get_npc(state, _require(params, "npc_id", expression))
        if npc is None:
            raise ConditionEvaluationError(expression, "unknown npc_id")
        return bool(get_value(npc, "alive", True))
    if predicate == "npc_realm":
        npc = get_npc(state, _require(params, "npc_id", expression))
        if npc is None:
            raise ConditionEvaluationError(expression, "unknown npc_id")
        return _entity_realm_at_least(state, npc, _require(params, "realm", expression))
    if predicate == "npc_relation":
        a = _require(params, "a", expression)
        b = _require(params, "b", expression)
        value = _require(params, "value", expression)
        return _compare(get_relation(state, a, b), value, str(params.get("op", ">=")))
    if predicate == "random_chance":
        chance = float(_require(params, "chance", expression))
        return (rng or random).random() < chance
    if predicate == "event_triggered":
        event_id = as_id(_require(params, "event_id", expression))
        return event_id in set(get_scenario_runtime(state).get("triggered_event_ids", []) or [])

    if predicate not in CANONICAL_PREDICATES:
        raise ConditionEvaluationError(expression, f"unknown predicate: {predicate}")
    raise ConditionEvaluationError(expression, f"unknown predicate: {predicate}")


def evaluate_condition(state: Any, expression: Any, *, rng: random.Random | None = None) -> bool:
    if expression is None:
        return True
    if not isinstance(expression, dict):
        raise ConditionEvaluationError(expression, "condition expression must be an object")
    if len(expression) != 1:
        raise ConditionEvaluationError(expression, "condition expression must contain exactly one predicate or operator")

    key, value = next(iter(expression.items()))
    if key == "all":
        if not isinstance(value, list):
            raise ConditionEvaluationError(expression, "all requires a list")
        return all(evaluate_condition(state, item, rng=rng) for item in value)
    if key == "any":
        if not isinstance(value, list):
            raise ConditionEvaluationError(expression, "any requires a list")
        return any(evaluate_condition(state, item, rng=rng) for item in value)
    if key == "not":
        return not evaluate_condition(state, value, rng=rng)
    return _eval_atomic(state, key, value, expression, rng=rng)
