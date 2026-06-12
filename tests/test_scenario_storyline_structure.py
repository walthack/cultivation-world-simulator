"""v1.6 P1-b — static structural validation of the storyline activation graph.

The spec promises load-time hard errors for reachable + mutually-exclusive
storylines. Reachability alone is not enough: a storyline that activates
itself is unreachable, activation cycles are unreachable, and sibling
storylines (the alternatives under one branch) must not be co-activatable on
a single runtime path. These are rejected at load.
"""

from __future__ import annotations

import pytest

from src.scenario.scenario_loader import ScenarioValidationError, _validate_storyline_structure


def _branch(event_id, *outcomes):
    """outcomes: (branch_id, storyline_to_activate)."""
    return {
        "id": event_id,
        "type": "branch",
        "trigger": {"year": 1, "month": 1, "condition": {"always": {}}},
        "branches": [
            {"id": bid, "condition": {"always": {}},
             "effects": [{"type": "activate_storyline", "storyline": sl}]}
            for bid, sl in outcomes
        ],
    }


def _beat(event_id, storyline, *, activates=None):
    effects = []
    if activates is not None:
        effects.append({"type": "activate_storyline", "storyline": activates})
    return {
        "id": event_id,
        "type": "side_event",
        "storyline": storyline,
        "trigger": {"year": 1, "month": 2, "condition": {"always": {}}},
        "effects": effects,
    }


def test_valid_exclusive_branch_tree_is_accepted():
    events = [
        _branch("fork", ("hardened", "line_h"), ("channel", "line_c")),
        _beat("h-beat", "line_h"),
        _beat("c-beat", "line_c"),
    ]
    _validate_storyline_structure(events)  # must not raise


def test_self_activating_storyline_rejected():
    events = [
        _branch("fork", ("a", "line_a")),
        _beat("a-beat", "line_a", activates="line_a"),  # line_a beat re-activates line_a
    ]
    with pytest.raises(ScenarioValidationError):
        _validate_storyline_structure(events)


def test_activation_cycle_rejected():
    events = [
        _branch("fork", ("a", "line_a")),
        _beat("a-beat", "line_a", activates="line_b"),  # line_a -> line_b
        _beat("b-beat", "line_b", activates="line_a"),  # line_b -> line_a  (cycle)
    ]
    with pytest.raises(ScenarioValidationError):
        _validate_storyline_structure(events)


def test_sibling_with_a_second_activator_rejected():
    events = [
        _branch("fork", ("hardened", "line_h"), ("channel", "line_c")),
        # a trunk event independently activates line_h → it is no longer exclusive
        {"id": "leak", "type": "side_event",
         "trigger": {"year": 1, "month": 1, "condition": {"always": {}}},
         "effects": [{"type": "activate_storyline", "storyline": "line_h"}]},
        _beat("h-beat", "line_h"),
        _beat("c-beat", "line_c"),
    ]
    with pytest.raises(ScenarioValidationError):
        _validate_storyline_structure(events)


def test_one_sibling_reaching_another_rejected():
    events = [
        _branch("fork", ("hardened", "line_h"), ("channel", "line_c")),
        _beat("h-beat", "line_h", activates="line_c"),  # picking line_h also activates sibling line_c
        _beat("c-beat", "line_c"),
    ]
    with pytest.raises(ScenarioValidationError):
        _validate_storyline_structure(events)
