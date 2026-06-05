from __future__ import annotations

from typing import Any, Awaitable, Callable

from .condition_evaluator import evaluate_condition
from .state_access import ensure_list, get_scenario_runtime, get_value


Handler = Callable[[Any, dict[str, Any]], Any | Awaitable[Any]]


class EventDispatcher:
    def __init__(self, timeline: list[dict[str, Any]], handlers: dict[str, Handler] | None = None):
        self.timeline = list(timeline or [])
        self.handlers = dict(handlers or {})

    async def dispatch_month(self, state: Any, *, year: int | None = None, month: int | None = None) -> list[dict[str, Any]]:
        world = get_value(state, "world", state)
        current_year = int(year if year is not None else get_value(world, "year", 0))
        current_month = int(month if month is not None else get_value(world, "month", 0))
        runtime = get_scenario_runtime(state)
        triggered = ensure_list(runtime, "triggered_event_ids")
        blocked = set(runtime.get("blocked_event_ids", []) or [])
        dispatched: list[dict[str, Any]] = []

        for event in self.timeline:
            event_id = str(event.get("id", "") or "")
            if not event_id or event_id in triggered or event_id in blocked:
                continue
            trigger = event.get("trigger", {}) or {}
            if int(trigger.get("year", -1)) != current_year or int(trigger.get("month", -1)) != current_month:
                continue
            if any(required not in triggered for required in event.get("requires_events", []) or []):
                continue
            if not evaluate_condition(state, trigger.get("condition")):
                continue

            handler = self.handlers.get(str(event.get("type", "")))
            if handler is not None:
                result = handler(state, event)
                if hasattr(result, "__await__"):
                    await result
            triggered.append(event_id)
            for blocked_event in event.get("blocks_events", []) or []:
                if blocked_event not in blocked:
                    blocked.add(blocked_event)
            runtime["blocked_event_ids"] = sorted(blocked)
            dispatched.append(event)
        return dispatched
