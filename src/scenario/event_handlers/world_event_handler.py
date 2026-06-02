from __future__ import annotations

from typing import Any

from .main_event_handler import ScenarioChoiceOutcome, resolve_scenario_event_choice
from ..effect_applier import apply_effects


async def handle_world_event(state: Any, event: dict[str, Any]) -> ScenarioChoiceOutcome | dict[str, Any]:
    if event.get("choices"):
        return await resolve_scenario_event_choice(state, event)
    apply_effects(state, event.get("effects", []) or [])
    return {"status": "ok", "event_id": event.get("id")}
