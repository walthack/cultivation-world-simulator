from __future__ import annotations

from typing import Any, Awaitable, Callable

from .condition_evaluator import evaluate_condition
from .state_access import ensure_list, get_active_storylines, get_scenario_runtime, get_value


Handler = Callable[[Any, dict[str, Any]], Any | Awaitable[Any]]
DISPATCH_LOG_LIMIT = 50


class EventDispatcher:
    def __init__(self, timeline: list[dict[str, Any]], handlers: dict[str, Handler] | None = None):
        self.timeline = list(timeline or [])
        self.handlers = dict(handlers or {})

    @staticmethod
    def _append_dispatch_log(
        runtime: dict[str, Any],
        *,
        month_stamp: str,
        event_id: str,
        fired: bool,
        reason: str | None = None,
    ) -> None:
        log = ensure_list(runtime, "dispatch_log")
        entry: dict[str, Any] = {
            "month_stamp": month_stamp,
            "event_id": event_id,
            "fired": fired,
        }
        if reason:
            entry["reason"] = reason
        log.append(entry)
        if len(log) > DISPATCH_LOG_LIMIT:
            del log[:-DISPATCH_LOG_LIMIT]

    async def dispatch_month(self, state: Any, *, year: int | None = None, month: int | None = None) -> list[dict[str, Any]]:
        world = get_value(state, "world", state)
        current_year = int(year if year is not None else get_value(world, "year", 0))
        current_month = int(month if month is not None else get_value(world, "month", 0))
        month_stamp = f"Y{current_year}M{current_month}"
        runtime = get_scenario_runtime(state)
        triggered = ensure_list(runtime, "triggered_event_ids")
        blocked = set(runtime.get("blocked_event_ids", []) or [])
        dispatched: list[dict[str, Any]] = []

        for event in self.timeline:
            event_id = str(event.get("id", "") or "")
            if not event_id:
                continue
            if event_id in triggered:
                self._append_dispatch_log(
                    runtime,
                    month_stamp=month_stamp,
                    event_id=event_id,
                    fired=False,
                    reason="already triggered",
                )
                continue
            if event_id in blocked:
                self._append_dispatch_log(
                    runtime,
                    month_stamp=month_stamp,
                    event_id=event_id,
                    fired=False,
                    reason="blocked",
                )
                continue
            trigger = event.get("trigger", {}) or {}
            if int(trigger.get("year", -1)) != current_year or int(trigger.get("month", -1)) != current_month:
                self._append_dispatch_log(
                    runtime,
                    month_stamp=month_stamp,
                    event_id=event_id,
                    fired=False,
                    reason="not scheduled for current month",
                )
                continue
            if any(required not in triggered for required in event.get("requires_events", []) or []):
                self._append_dispatch_log(
                    runtime,
                    month_stamp=month_stamp,
                    event_id=event_id,
                    fired=False,
                    reason="required event not triggered",
                )
                continue
            storyline = event.get("storyline")
            if storyline is not None and storyline not in get_active_storylines(state):
                self._append_dispatch_log(
                    runtime,
                    month_stamp=month_stamp,
                    event_id=event_id,
                    fired=False,
                    reason="storyline inactive",
                )
                continue
            if not evaluate_condition(state, trigger.get("condition")):
                self._append_dispatch_log(
                    runtime,
                    month_stamp=month_stamp,
                    event_id=event_id,
                    fired=False,
                    reason="condition failed",
                )
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
            self._append_dispatch_log(
                runtime,
                month_stamp=month_stamp,
                event_id=event_id,
                fired=True,
            )
            dispatched.append(event)
        return dispatched
