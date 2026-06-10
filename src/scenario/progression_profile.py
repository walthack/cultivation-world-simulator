from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.run.log import get_logger


logger = get_logger().logger


DEFAULT_PROGRESSION_PROFILE: dict[str, Any] = {
    "id": "cultivation",
    "label": "修真境界",
    "guidance": "长期目标可围绕修炼积累、突破境界与仙途发展，并结合角色身份和处境。",
    "axes": [
        {
            "id": "cultivation_realm",
            "label": "修真境界",
            "description": "以修为积累和境界突破衡量个人成长。",
            "tiers": ["练气", "筑基", "金丹", "元婴"],
            "optional": False,
        }
    ],
}


def resolve_progression_profile(world: Any) -> dict[str, Any]:
    scenario = getattr(world, "scripted_scenario", None)
    generation_profile = getattr(scenario, "generation_profile", None)
    if isinstance(generation_profile, dict):
        profile = generation_profile.get("progression_profile")
        if isinstance(profile, dict):
            return deepcopy(profile)
    return deepcopy(DEFAULT_PROGRESSION_PROFILE)


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_valid_profile(profile: Any) -> bool:
    if not isinstance(profile, dict):
        return False
    if not _is_non_empty_string(profile.get("id")) or not _is_non_empty_string(profile.get("label")):
        return False
    guidance = profile.get("guidance")
    if guidance is not None and not _is_non_empty_string(guidance):
        return False
    axes = profile.get("axes")
    if not isinstance(axes, list) or not axes:
        return False
    for axis in axes:
        if not isinstance(axis, dict):
            return False
        if not all(_is_non_empty_string(axis.get(key)) for key in ("id", "label", "description")):
            return False
        tiers = axis.get("tiers")
        if not isinstance(tiers, list) or not tiers or not all(_is_non_empty_string(tier) for tier in tiers):
            return False
        if "optional" in axis and not isinstance(axis["optional"], bool):
            return False
    return True


def build_progression_context(world: Any) -> str:
    profile = resolve_progression_profile(world)
    if not _is_valid_profile(profile):
        scenario_id = getattr(getattr(world, "scripted_scenario", None), "scenario_id", "unknown")
        logger.warning(
            "Scenario %s has a malformed progression_profile; using default cultivation progression context",
            scenario_id,
        )
        profile = deepcopy(DEFAULT_PROGRESSION_PROFILE)
    lines = [f"成长体系：{profile['label']}（{profile['id']}）"]
    guidance = str(profile.get("guidance") or "").strip()
    if guidance:
        lines.append(f"目标指引：{guidance}")

    for axis in profile["axes"]:
        role = "可选共存轴" if axis.get("optional", False) else "主要成长轴"
        tiers = " → ".join(str(tier) for tier in axis["tiers"])
        line = f"- {axis['label']} [{role}]：{axis['description']}"
        if tiers:
            line += f"；层级：{tiers}"
        lines.append(line)
    return "\n".join(lines)
