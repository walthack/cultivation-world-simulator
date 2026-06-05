from __future__ import annotations

from typing import Any, Dict


def _get_mapping_value(data: Any, key: str, default: Any = None) -> Any:
    if isinstance(data, dict):
        return data.get(key, default)
    return default


def _build_timeline_event(event: dict[str, Any], triggered_events: set[str], triggered_months: dict[str, Any]) -> dict[str, Any]:
    event_id = str(event.get("id") or "")
    trigger = event.get("trigger") if isinstance(event.get("trigger"), dict) else {}
    item: dict[str, Any] = {
        "id": event_id,
        "name": str(event.get("name") or event_id),
        "type": str(event.get("type") or ""),
        "trigger": {
            "year": trigger.get("year"),
            "month": trigger.get("month"),
        },
        "dynasty_id": event.get("dynasty_id"),
        "at_region_id": trigger.get("at_region_id"),
        "triggered": event_id in triggered_events,
    }
    if event_id in triggered_months:
        item["triggered_month_stamp"] = str(triggered_months[event_id])
    return item


def build_scenario_status(world: Any, resolved_scenario: Any | None = None) -> Dict[str, Any]:
    scripted_scenario = getattr(world, "scripted_scenario", None) if world is not None else None
    if scripted_scenario is None:
        return {"active": False}

    state = getattr(scripted_scenario, "state", {}) or {}
    triggered_events = {str(item) for item in (getattr(scripted_scenario, "triggered_events", set()) or set())}
    triggered_months = _get_mapping_value(state, "triggered_month_stamps", {})
    if not isinstance(triggered_months, dict):
        triggered_months = {}

    timeline = list(getattr(scripted_scenario, "timeline", []) or [])
    events = [
        _build_timeline_event(event, triggered_events, triggered_months)
        for event in timeline
        if isinstance(event, dict)
    ]
    scenario_data = getattr(resolved_scenario, "scenario", {}) or {}

    return {
        "active": True,
        "scenario_id": str(getattr(scripted_scenario, "scenario_id", "") or ""),
        "title": str(getattr(resolved_scenario, "title", "") or scenario_data.get("title") or ""),
        "version": str(getattr(resolved_scenario, "version", "") or scenario_data.get("version") or ""),
        "world_background": str(scenario_data.get("world_background") or ""),
        "preset_id": str(getattr(resolved_scenario, "preset_id", "") or _get_mapping_value(scenario_data.get("world_preset"), "preset_id", "")),
        "controlled_avatar": state.get("controlled_avatar"),
        "timeline": {
            "total_events": len(events),
            "triggered_count": sum(1 for event in events if event["triggered"]),
            "events": events,
        },
        "world_flags": dict(state.get("world_flags", {}) or {}),
    }
