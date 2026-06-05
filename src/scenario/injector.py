from __future__ import annotations

from typing import Any

from src.scenario.scenario_loader import ResolvedScenario
from src.scenario.state import ScriptedScenarioState


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
        state=_build_initial_scenario_state(resolved),
    )
