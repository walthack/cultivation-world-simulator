from __future__ import annotations

from typing import Any

from ..effect_applier import apply_effects


async def handle_relation_change(state: Any, event: dict[str, Any]) -> dict[str, Any]:
    effects = event.get("effects")
    if effects is None:
        effects = [
            {
                "type": "relation_change",
                "a": event.get("a"),
                "b": event.get("b"),
                "delta": event.get("delta", 0),
            }
        ]
    apply_effects(state, effects or [])
    return {"status": "ok", "event_id": event.get("id")}
