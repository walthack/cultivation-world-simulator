from __future__ import annotations

from typing import Any

from src.classes.relation.relation import RelationState
from src.scenario.scenario_loader import ResolvedScenario
from src.scenario.state import ScriptedScenarioState
from src.sim.avatar_init import create_scenario_avatar


def _build_initial_scenario_state(resolved: ResolvedScenario) -> dict[str, Any]:
    initial = resolved.scenario.get("initial_state", {}) or {}
    avatars = {
        str(avatar.get("id")): {
            "id": str(avatar.get("id")),
            "name": f"{avatar.get('surname', '')}{avatar.get('given_name', '')}",
            "realm": avatar.get("realm"),
            "alive": True,
            "skills": [],
            "stats": {},
            "items": [],
            "sect_id": avatar.get("sect_id"),
        }
        for avatar in initial.get("avatars", []) or []
        if avatar.get("id")
    }
    relations: dict[str, int] = {}
    for relation in initial.get("relationships", []) or []:
        a = str(relation.get("a") or "")
        b = str(relation.get("b") or "")
        if not a or not b:
            continue
        left, right = sorted([a, b])
        relations[f"{left}:{right}"] = int(relation.get("value", 0) or 0)

    return {
        "realm_order": [
            "LIAN_QI",
            "ZHU_JI",
            "JIE_DAN",
            "YUAN_YING",
            "HUA_SHEN",
            "LIAN_XU",
            "HE_TI",
            "DU_JIE",
            "DA_CHENG",
        ],
        "npcs": avatars,
        "relations": relations,
        "world_flags": dict(initial.get("world_flags", {}) or {}),
    }


def inject_scenario_into_world(world: Any, resolved: ResolvedScenario) -> None:
    world.scripted_scenario = ScriptedScenarioState(
        scenario_id=resolved.scenario_id,
        timeline=list(resolved.timeline or []),
        generation_profile=resolved.generation_profile,
        state=_build_initial_scenario_state(resolved),
    )


def inject_scenario_initial_state_into_world(world: Any, resolved: ResolvedScenario) -> None:
    initial = resolved.scenario.get("initial_state", {}) or {}
    avatars = list(initial.get("avatars", []) or [])
    relationships = list(initial.get("relationships", []) or [])

    for item in avatars:
        avatar = create_scenario_avatar(
            world,
            item,
            world.month_stamp,
            preset_id=resolved.preset_id,
        )
        world.avatar_manager.register_avatar(avatar, is_newly_born=True)

    for item in relationships:
        avatar_a = world.avatar_manager.get_avatar(str(item.get("a") or ""))
        avatar_b = world.avatar_manager.get_avatar(str(item.get("b") or ""))
        if avatar_a is None or avatar_b is None:
            raise ValueError(f"Scenario relationship references missing avatar: {item}")

        value = int(item.get("value", 0) or 0)
        avatar_a.relations[avatar_b] = RelationState(friendliness=value)
        avatar_b.relations[avatar_a] = RelationState(friendliness=value)
