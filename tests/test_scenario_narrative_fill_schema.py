"""v1.7 M1 — narrative_fill schema validation (Q6 + Q2 at load time).

`narrative_fill` is an explicit boolean opt-in. When true, the event must carry
an authored `narration_fallback` string (not description reuse) — the permanent
fallback used on LLM failure / cache miss. Both are validated in one loader pass.
"""

from __future__ import annotations

import pytest

from src.scenario.scenario_loader import ScenarioValidationError, _validate_narrative_fill


def _event(**over):
    e = {"id": "e", "type": "side_event", "trigger": {"year": 1, "month": 1, "condition": {"always": {}}}}
    e.update(over)
    return e


def test_event_without_narrative_fill_is_fine():
    _validate_narrative_fill(_event(), "timeline.events[0]")  # no raise


def test_narrative_fill_false_needs_no_fallback():
    _validate_narrative_fill(_event(narrative_fill=False), "timeline.events[0]")


def test_narrative_fill_must_be_a_real_boolean():
    for bad in ("true", 1, "1", {}):
        with pytest.raises(ScenarioValidationError):
            _validate_narrative_fill(_event(narrative_fill=bad), "timeline.events[0]")


def test_narrative_fill_true_requires_authored_fallback():
    with pytest.raises(ScenarioValidationError):
        _validate_narrative_fill(_event(narrative_fill=True), "timeline.events[0]")


def test_narration_fallback_must_be_non_empty_string():
    with pytest.raises(ScenarioValidationError):
        _validate_narrative_fill(_event(narrative_fill=True, narration_fallback="  "), "timeline.events[0]")


def test_valid_narrative_fill_event_passes():
    _validate_narrative_fill(
        _event(narrative_fill=True, narration_fallback="程宗扬立于草原，远处秦军方阵未动。"),
        "timeline.events[0]",
    )
