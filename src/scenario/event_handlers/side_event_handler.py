from __future__ import annotations

from typing import Any

from ..effect_applier import apply_effects


async def handle_side_event(state: Any, event: dict[str, Any]) -> dict[str, Any]:
    apply_effects(state, event.get("effects", []) or [])
    return {"status": "ok", "event_id": event.get("id")}
