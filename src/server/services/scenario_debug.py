from __future__ import annotations

from typing import Any


def _scenario(world: Any) -> Any | None:
    return getattr(world, "scripted_scenario", None) if world is not None else None


def get_debug_snapshot(world: Any) -> dict[str, Any]:
    scripted_scenario = _scenario(world)
    if scripted_scenario is None:
        return {
            "state": {},
            "triggered_events": [],
            "dispatch_log": [],
        }

    return {
        "state": dict(getattr(scripted_scenario, "state", {}) or {}),
        "triggered_events": sorted(str(item) for item in (getattr(scripted_scenario, "triggered_events", set()) or set())),
        "dispatch_log": [
            {
                key: value
                for key, value in dict(item).items()
                if key in {"month_stamp", "event_id", "fired", "reason"}
            }
            for item in list(getattr(scripted_scenario, "dispatch_log", []) or [])[-50:]
            if isinstance(item, dict)
        ],
    }
