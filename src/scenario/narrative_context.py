from __future__ import annotations

from typing import Any


_FIELD_LABELS = (
    ("background", "Background"),
    ("style", "Style"),
    ("terminology", "Terminology"),
)


def build_scenario_context_block(world: Any) -> str:
    scripted_scenario = getattr(world, "scripted_scenario", None)
    if scripted_scenario is None:
        return ""

    generation_profile = getattr(scripted_scenario, "generation_profile", None)
    if not isinstance(generation_profile, dict) or not generation_profile:
        return ""

    narrative_context = generation_profile.get("narrative_context")
    if not isinstance(narrative_context, dict) or not narrative_context:
        return ""

    lines = []
    for key, label in _FIELD_LABELS:
        value = str(narrative_context.get(key) or "").strip()
        if value:
            lines.append(f"- {label}: {value}")

    if not lines:
        return ""
    return "Scenario narrative context:\n" + "\n".join(lines)


def append_scenario_context(base_text: str, world: Any) -> str:
    block = build_scenario_context_block(world)
    if not block:
        return base_text

    normalized_base = str(base_text or "").strip()
    if not normalized_base:
        return block
    if block in normalized_base:
        return normalized_base
    return f"{normalized_base}\n\n{block}"


def prepend_scenario_context(base_text: str, world: Any) -> str:
    block = build_scenario_context_block(world)
    if not block:
        return base_text

    normalized_base = str(base_text or "").strip()
    if not normalized_base:
        return block
    if block in normalized_base:
        return normalized_base
    return f"{block}\n\n{normalized_base}"
