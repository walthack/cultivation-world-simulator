"""v1.8 M0 — `anchor` schema validation.

`anchor` is an explicit boolean marking an event as part of the deterministic
backbone the LLM may not cross. Validated in the same loader pass as the rest of
the per-event schema.
"""

from __future__ import annotations

import pytest

from src.scenario.scenario_loader import ScenarioValidationError, _validate_anchor


def _event(**over):
    e = {"id": "e", "type": "side_event", "trigger": {"year": 1, "month": 1, "condition": {"always": {}}}}
    e.update(over)
    return e


def test_event_without_anchor_is_fine():
    _validate_anchor(_event(), "timeline.events[0]")  # no raise


def test_anchor_true_passes():
    _validate_anchor(_event(anchor=True), "timeline.events[0]")


def test_anchor_must_be_a_real_boolean():
    for bad in ("true", 1, "1", {}):
        with pytest.raises(ScenarioValidationError):
            _validate_anchor(_event(anchor=bad), "timeline.events[0]")
