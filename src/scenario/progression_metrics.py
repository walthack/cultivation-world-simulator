from __future__ import annotations

from typing import Any

from src.run.log import get_logger
from src.scenario.progression_profile import DEFAULT_PROGRESSION_PROFILE, resolve_progression_profile


DEFAULT_RESIDUAL_TERMS = ("金丹", "元婴", "结丹", "筑基", "练气", "炼气", "化神", "渡劫", "飞升")


def _axis_terms(axis: dict[str, Any]) -> tuple[str, ...]:
    values = [axis.get("label", ""), *(axis.get("tiers") or [])]
    return tuple(str(value).strip() for value in values if str(value).strip())


def _mentioned_axis_ids(profile: dict[str, Any], text: str) -> set[str]:
    return {
        str(axis["id"])
        for axis in profile.get("axes", [])
        if isinstance(axis, dict) and any(term in text for term in _axis_terms(axis))
    }


def build_progression_metrics(
    world: Any,
    output: str,
    *,
    goal_text: str = "",
    behavior_text: str = "",
) -> dict[str, int | float | bool | None]:
    profile = resolve_progression_profile(world)
    output = str(output or "")
    is_default = profile.get("id") == DEFAULT_PROGRESSION_PROFILE["id"]
    declared_terms = {
        term
        for axis in profile.get("axes", [])
        if isinstance(axis, dict)
        for term in _axis_terms(axis)
    }
    residual_terms = (term for term in DEFAULT_RESIDUAL_TERMS if term not in declared_terms)
    residual_count = 0 if is_default else sum(output.count(term) for term in residual_terms)
    metrics: dict[str, int | float | bool | None] = {
        "progression.output_count": 1,
        "progression.profile_selected_count": 0 if is_default else 1,
        "progression.default_residual_count": residual_count,
        "progression.default_residual_rate": float(residual_count > 0),
        "progression.goal_behavior_consistent": None,
    }
    for axis in profile.get("axes", []):
        if not isinstance(axis, dict) or not axis.get("id"):
            continue
        metrics[f"progression.axis_mentions.{axis['id']}"] = sum(
            output.count(term) for term in _axis_terms(axis)
        )

    if goal_text and behavior_text:
        goal_axes = _mentioned_axis_ids(profile, goal_text)
        behavior_axes = _mentioned_axis_ids(profile, behavior_text)
        metrics["progression.goal_behavior_consistent"] = bool(
            residual_count == 0 and goal_axes and goal_axes.intersection(behavior_axes)
        )
    return metrics


def record_progression_metrics(
    world: Any,
    output: str,
    *,
    goal_text: str = "",
    behavior_text: str = "",
) -> None:
    get_logger().log_progression_metrics(
        build_progression_metrics(
            world,
            output,
            goal_text=goal_text,
            behavior_text=behavior_text,
        )
    )
