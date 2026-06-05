from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScriptedScenarioState:
    scenario_id: str
    timeline: list[dict[str, Any]]
    state: dict[str, Any] = field(default_factory=dict)
    triggered_events: set[str] = field(default_factory=set)
    dispatch_log: list[dict[str, Any]] = field(default_factory=list)
