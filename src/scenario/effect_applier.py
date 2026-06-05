from __future__ import annotations

import copy
import logging
from typing import Any, Callable

from src.scenario.scenario_loader import MissingReferenceError

from .schema_constants import CANONICAL_EFFECT_TYPES
from .state_access import (
    as_id,
    ensure_dict,
    ensure_list,
    get_npc,
    get_npcs,
    get_player,
    get_relation,
    get_scenario_runtime,
    get_scenario_vars,
    get_value,
    get_world_flags,
    set_relation,
    set_value,
)


logger = logging.getLogger(__name__)


class EffectError(ValueError):
    pass


EffectFn = Callable[[Any, dict[str, Any]], None]
_EFFECT_REGISTRY: dict[str, tuple[EffectFn, str]] = {}


def register_effect(name: str, fn: EffectFn, *, source: str = "mod") -> None:
    normalized = str(name)
    if normalized in CANONICAL_EFFECT_TYPES or normalized in _EFFECT_REGISTRY:
        raise EffectError(f"Effect already registered: {normalized}")
    _EFFECT_REGISTRY[normalized] = (fn, source)


def unregister_effect(name: str) -> None:
    _EFFECT_REGISTRY.pop(str(name), None)


def reset_effect_registry() -> None:
    _EFFECT_REGISTRY.clear()


def get_registered_effects() -> dict[str, str]:
    return {name: source for name, (_, source) in _EFFECT_REGISTRY.items()}


def _require(effect: dict[str, Any], key: str) -> Any:
    if key not in effect:
        raise EffectError(f"Missing effect parameter: {key}")
    return effect[key]


def _require_npc(state: Any, npc_id: Any) -> Any:
    npc = get_npc(state, as_id(npc_id))
    if npc is None:
        raise MissingReferenceError("effect.npc_id", npc_id, "state.npcs")
    return npc


def _skills(entity: Any) -> list[Any]:
    return ensure_list(entity, "skills")


def _items(entity: Any) -> list[Any]:
    return ensure_list(entity, "items")


def _stats(entity: Any) -> dict[str, Any]:
    return ensure_dict(entity, "stats")


def _controlled_avatar(state: Any) -> str:
    controlled_avatar = get_value(state, "controlled_avatar")
    if controlled_avatar is None:
        raise EffectError("Missing state placeholder: controlled_avatar")
    return str(controlled_avatar)


def _substitute_placeholders(state: Any, value: Any) -> Any:
    if isinstance(value, str) and "{controlled_avatar}" in value:
        return value.replace("{controlled_avatar}", _controlled_avatar(state))
    if isinstance(value, list):
        return [_substitute_placeholders(state, item) for item in value]
    if isinstance(value, dict):
        return {key: _substitute_placeholders(state, item) for key, item in value.items()}
    return value


def _apply_one(state: Any, effect: dict[str, Any]) -> None:
    effect = _substitute_placeholders(state, effect)
    effect_type = str(_require(effect, "type"))
    player = get_player(state)

    if effect_type == "gain_skill":
        skill = _require(effect, "skill")
        if skill not in _skills(player):
            _skills(player).append(skill)
        return
    if effect_type == "lose_skill":
        skill = _require(effect, "skill")
        if skill in _skills(player):
            _skills(player).remove(skill)
        return
    if effect_type == "gain_stat":
        stat = str(_require(effect, "stat"))
        _stats(player)[stat] = int(_stats(player).get(stat, 0) or 0) + int(_require(effect, "amount"))
        return
    if effect_type == "lose_stat":
        stat = str(_require(effect, "stat"))
        _stats(player)[stat] = int(_stats(player).get(stat, 0) or 0) - int(_require(effect, "amount"))
        return
    if effect_type == "set_stat":
        _stats(player)[str(_require(effect, "stat"))] = _require(effect, "value")
        return
    if effect_type == "gain_item":
        item = _require(effect, "item")
        _items(player).append(item)
        return
    if effect_type == "lose_item":
        item = _require(effect, "item")
        if item in _items(player):
            _items(player).remove(item)
        return
    if effect_type == "set_flag":
        get_world_flags(state)[str(_require(effect, "flag"))] = True
        return
    if effect_type == "clear_flag":
        get_world_flags(state).pop(str(_require(effect, "flag")), None)
        return
    if effect_type == "npc_join":
        npc = _require_npc(state, _require(effect, "npc_id"))
        set_value(npc, "joined", True)
        return
    if effect_type == "npc_leave":
        npc = _require_npc(state, _require(effect, "npc_id"))
        set_value(npc, "joined", False)
        return
    if effect_type == "npc_die":
        npc = _require_npc(state, _require(effect, "npc_id"))
        set_value(npc, "alive", False)
        return
    if effect_type == "npc_set_realm":
        npc = _require_npc(state, _require(effect, "npc_id"))
        set_value(npc, "realm", _require(effect, "realm"))
        return
    if effect_type == "npc_set_relation":
        set_relation(state, _require(effect, "a"), _require(effect, "b"), int(_require(effect, "value")))
        return
    if effect_type == "relation_change":
        a = _require(effect, "a")
        b = _require(effect, "b")
        set_relation(state, a, b, get_relation(state, a, b) + int(_require(effect, "delta")))
        return
    if effect_type == "world_event_trigger":
        runtime = get_scenario_runtime(state)
        triggered = ensure_list(runtime, "triggered_event_ids")
        event_id = as_id(_require(effect, "event_id"))
        if event_id and event_id not in triggered:
            triggered.append(event_id)
        return
    if effect_type == "economy_event":
        logger.info("Scenario economy_event no-op: %s", effect)
        return
    if effect_type == "set_var":
        get_scenario_vars(state)[str(_require(effect, "name"))] = _require(effect, "value")
        return

    registered = _EFFECT_REGISTRY.get(effect_type)
    if registered is not None:
        fn, _ = registered
        fn(state, effect)
        return

    if effect_type not in CANONICAL_EFFECT_TYPES:
        raise EffectError(f"Unknown effect type: {effect_type}")
    raise EffectError(f"Unhandled canonical effect type: {effect_type}")


def apply_effects(state: Any, effects: list[dict[str, Any]]) -> Any:
    if not isinstance(effects, list):
        raise EffectError("effects must be a list")

    before = copy.deepcopy(state)
    try:
        for effect in effects:
            if not isinstance(effect, dict):
                raise EffectError(f"effect must be an object: {effect!r}")
            _apply_one(state, effect)
    except Exception:
        if isinstance(state, dict) and isinstance(before, dict):
            state.clear()
            state.update(before)
        raise
    return state


def spawn_npc(state: Any, npc: dict[str, Any]) -> None:
    npc_id = as_id(_require(npc, "id"))
    npcs = get_npcs(state)
    if npc_id in npcs:
        raise EffectError(f"NPC already exists: {npc_id}")
    npcs[npc_id] = dict(npc)
