from __future__ import annotations

from typing import Any

from ..effect_applier import spawn_npc


async def handle_character_introduction(state: Any, event: dict[str, Any]) -> dict[str, Any]:
    npc = event.get("spawn_avatar") or event.get("npc")
    if npc:
        spawn_npc(state, npc)
    return {"status": "ok", "event_id": event.get("id"), "spawned": npc}
