from __future__ import annotations

from typing import Any


_FIELD_LABELS = (
    ("background", "Background"),
    ("style", "Style"),
    ("terminology", "Terminology"),
)

SCENARIO_NARRATIVE_INSTRUCTION = (
    "严格按该时代风格叙事，避免修真宗门/秘境/境界等修仙术语，以六朝士族门阀风貌行文。"
)


def _get_generation_profile(world: Any) -> dict[str, Any]:
    scripted_scenario = getattr(world, "scripted_scenario", None)
    generation_profile = getattr(scripted_scenario, "generation_profile", None)
    if not isinstance(generation_profile, dict):
        return {}
    return generation_profile


def _get_narrative_context(world: Any) -> dict[str, Any]:
    narrative_context = _get_generation_profile(world).get("narrative_context")
    if not isinstance(narrative_context, dict):
        return {}
    return narrative_context


def apply_scenario_term_map(text: str, world: Any) -> str:
    term_map = _get_generation_profile(world).get("term_map")
    if not isinstance(term_map, dict):
        return text

    mapped = text
    for source_term, replacement in term_map.items():
        if isinstance(source_term, str) and isinstance(replacement, str):
            mapped = mapped.replace(source_term, replacement)
    return mapped


def _get_world_lore_mode(world: Any) -> str:
    mode = _get_narrative_context(world).get("world_lore_mode", "append")
    return str(mode or "append")


def _with_strong_instruction(block: str, world: Any) -> str:
    if not block or _get_world_lore_mode(world) == "append":
        return block
    return f"{SCENARIO_NARRATIVE_INSTRUCTION}\n\n{block}"


def build_scenario_context_block(world: Any) -> str:
    narrative_context = _get_narrative_context(world)
    if not narrative_context:
        return ""

    lines = []
    for key, label in _FIELD_LABELS:
        value = str(narrative_context.get(key) or "").strip()
        if value:
            lines.append(f"- {label}: {apply_scenario_term_map(value, world)}")

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
    block = _with_strong_instruction(build_scenario_context_block(world), world)
    if not block:
        return base_text

    normalized_base = str(base_text or "").strip()
    if not normalized_base:
        return block
    if block in normalized_base:
        return normalized_base
    return f"{block}\n\n{normalized_base}"


def build_prompt_world_lore(base_text: str, world: Any) -> str:
    narrative_context = _get_narrative_context(world)
    mode = _get_world_lore_mode(world)
    scenario_world_lore = apply_scenario_term_map(
        str(narrative_context.get("world_lore") or "").strip(),
        world,
    )
    block = build_scenario_context_block(world)
    scenario_text = "\n\n".join(section for section in (block, scenario_world_lore) if section)

    if mode == "replace":
        return _with_strong_instruction(scenario_text, world)

    if mode == "prepend" and scenario_text:
        scenario_text = _with_strong_instruction(scenario_text, world)
        normalized_base = str(base_text or "").strip()
        return f"{scenario_text}\n\n{normalized_base}" if normalized_base else scenario_text

    if scenario_world_lore:
        normalized_base = str(base_text or "").strip()
        sections = [section for section in (normalized_base, scenario_text) if section]
        return "\n\n".join(sections)

    return append_scenario_context(base_text, world)
