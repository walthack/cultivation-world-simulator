from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScriptedScenarioState:
    scenario_id: str
    timeline: list[dict[str, Any]]
    generation_profile: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)
    triggered_events: set[str] = field(default_factory=set)
    dispatch_log: list[dict[str, Any]] = field(default_factory=list)
    # v1.7 M2 (Q3): reproducible render-only narration cache, keyed by
    # (scenario_id, event_id, resolved_outcome, content_locale). Deliberately a
    # SIBLING of `state` — never inside it — so conditions/var_equals can't read
    # generated text (Q12). Persisted to the save as its own field.
    narration_cache: dict[str, str] = field(default_factory=dict)
