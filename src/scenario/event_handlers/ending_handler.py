from __future__ import annotations

from typing import Any

from ..state_access import get_scenario_runtime


async def handle_ending(state: Any, event: dict[str, Any]) -> dict[str, Any]:
    runtime = get_scenario_runtime(state)
    runtime["ending"] = {
        "event_id": event.get("id"),
        "outcome_text": event.get("outcome_text", ""),
    }
    return {"status": "ok", "event_id": event.get("id")}
