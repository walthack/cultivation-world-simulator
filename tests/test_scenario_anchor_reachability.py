"""v1.8 M1 — load-time TIMED anchor-chain reachability.

v1.6's reachability validation is structural only (an activator exists, no cycles,
sibling-activator count). It never checks *timing*, so a starvation hole survives
load: an anchor whose required event fires AFTER the anchor's own exact-month
window can never trigger (dispatch is one-shot per month), and a same-month
required event listed AFTER the anchor in author order is skipped on the single
dispatch pass. M1 turns both into load-time hard errors for anchors — the
deterministic backbone the LLM may not cross must be provably reachable.
"""

from __future__ import annotations

import pytest

from src.scenario.scenario_loader import ScenarioValidationError, _validate_anchor_reachability


def _ev(eid, year, month, *, anchor=False, requires=None):
    e = {
        "id": eid,
        "type": "side_event",
        "trigger": {"year": year, "month": month, "condition": {"always": {}}},
    }
    if anchor:
        e["anchor"] = True
    if requires:
        e["requires_events"] = list(requires)
    return e


def test_anchor_with_earlier_requirement_passes():
    events = [
        _ev("a", 1, 1),
        _ev("b", 1, 5, anchor=True, requires=["a"]),
    ]
    _validate_anchor_reachability(events)  # no raise


def test_anchor_requiring_a_later_event_is_rejected():
    events = [
        _ev("late", 2, 3),
        _ev("anchor", 1, 5, anchor=True, requires=["late"]),
    ]
    with pytest.raises(ScenarioValidationError):
        _validate_anchor_reachability(events)


def test_same_month_requirement_listed_after_anchor_is_rejected():
    # anchor B requires A, both in month 5, but A is authored AFTER B → single-pass
    # dispatch evaluates B before A is triggered → B starves.
    events = [
        _ev("b", 1, 5, anchor=True, requires=["a"]),
        _ev("a", 1, 5),
    ]
    with pytest.raises(ScenarioValidationError):
        _validate_anchor_reachability(events)


def test_same_month_requirement_listed_before_anchor_passes():
    events = [
        _ev("a", 1, 5),
        _ev("b", 1, 5, anchor=True, requires=["a"]),
    ]
    _validate_anchor_reachability(events)  # no raise


def test_non_anchor_requirer_is_not_subject_to_timed_check():
    # the timed check guards the anchor BACKBONE only; ordinary v1.6 events keep
    # their existing (looser) behavior — this is not an M1 regression target.
    events = [
        _ev("late", 2, 3),
        _ev("ordinary", 1, 5, requires=["late"]),
    ]
    _validate_anchor_reachability(events)  # no raise


def test_anchor_requiring_another_anchor_respects_timing():
    events = [
        _ev("a1", 1, 1, anchor=True),
        _ev("a2", 1, 2, anchor=True, requires=["a1"]),
    ]
    _validate_anchor_reachability(events)  # no raise


def test_transitive_requirement_timing_is_enforced():
    # A@M5 requires B@M4 (ok), but B requires C@M6 (broken) → B misses → A starves.
    events = [
        _ev("c", 1, 6),
        _ev("b", 1, 4, requires=["c"]),
        _ev("a", 1, 5, anchor=True, requires=["b"]),
    ]
    with pytest.raises(ScenarioValidationError):
        _validate_anchor_reachability(events)


def test_requires_cycle_in_anchor_closure_is_rejected():
    events = [
        _ev("b", 1, 4, requires=["a"]),
        _ev("a", 1, 5, anchor=True, requires=["b"]),
    ]
    with pytest.raises(ScenarioValidationError):
        _validate_anchor_reachability(events)


def test_non_anchor_node_inside_an_anchor_closure_is_checked():
    # entering an anchor's dependency closure tightens an otherwise-loose non-anchor
    events = [
        _ev("late", 2, 1),
        _ev("mid", 1, 4, requires=["late"]),     # non-anchor, but in A's closure
        _ev("a", 1, 5, anchor=True, requires=["mid"]),
    ]
    with pytest.raises(ScenarioValidationError):
        _validate_anchor_reachability(events)
