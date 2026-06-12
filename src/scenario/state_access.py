from __future__ import annotations

from typing import Any


def get_value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def set_value(obj: Any, key: str, value: Any) -> None:
    if isinstance(obj, dict):
        obj[key] = value
        return
    setattr(obj, key, value)


def ensure_dict(obj: Any, key: str) -> dict[str, Any]:
    current = get_value(obj, key)
    if isinstance(current, dict):
        return current
    current = {}
    set_value(obj, key, current)
    return current


def ensure_list(obj: Any, key: str) -> list[Any]:
    current = get_value(obj, key)
    if isinstance(current, list):
        return current
    current = []
    set_value(obj, key, current)
    return current


def as_id(value: Any) -> str:
    return str(value or "").strip()


def get_player(state: Any) -> Any:
    return get_value(state, "player")


def get_world(state: Any) -> Any:
    return get_value(state, "world", state)


def get_npcs(state: Any) -> dict[str, Any]:
    npcs = get_value(state, "npcs", {})
    return npcs if isinstance(npcs, dict) else {}


def get_npc(state: Any, npc_id: str) -> Any:
    return get_npcs(state).get(as_id(npc_id))


def get_world_flags(state: Any) -> dict[str, Any]:
    world = get_world(state)
    return ensure_dict(world, "world_flags")


def get_relations(state: Any) -> dict[str, int]:
    return ensure_dict(state, "relations")


def relation_key(a: Any, b: Any) -> str:
    a_id = as_id(a)
    b_id = as_id(b)
    left, right = sorted([a_id, b_id])
    return f"{left}:{right}"


def get_relation(state: Any, a: Any, b: Any) -> int:
    return int(get_relations(state).get(relation_key(a, b), 0) or 0)


def set_relation(state: Any, a: Any, b: Any, value: int) -> None:
    get_relations(state)[relation_key(a, b)] = int(value)


def get_scenario_runtime(state: Any) -> dict[str, Any]:
    return ensure_dict(state, "scenario_runtime")


def get_scenario_vars(state: Any) -> dict[str, Any]:
    explicit_state = get_value(state, "scripted_scenario_state")
    if isinstance(explicit_state, dict):
        return explicit_state

    world = get_world(state)
    scripted_scenario = get_value(world, "scripted_scenario")
    scripted_state = get_value(scripted_scenario, "state") if scripted_scenario is not None else None
    if isinstance(scripted_state, dict):
        return scripted_state

    return get_scenario_runtime(state)


def get_active_storylines(state: Any) -> list[Any]:
    """v1.6 step B: storyline ids currently active. An event tagged with a
    `storyline` only dispatches while that id is in this set."""
    return ensure_list(get_scenario_runtime(state), "active_storylines")
