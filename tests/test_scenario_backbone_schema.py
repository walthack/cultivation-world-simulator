"""v1.9 M1b — `backbone` schema validation (L4 Q1/Q4).

The immutable backbone declares machine-checkable hard gates: `prohibited_predicates`
(condition expressions the director must never make true) and `irreversible_facts`
(condition expressions that, once true, the director must never reverse). Both are
shape-validated in the same loader pass as the rest of the scenario top level.
"""

from __future__ import annotations

import pytest

from src.scenario.scenario_loader import ScenarioValidationError, _validate_backbone


def test_absent_backbone_is_allowed():
    _validate_backbone({})  # no backbone → no-op


def test_valid_backbone_passes():
    _validate_backbone({
        "backbone": {
            "prohibited_predicates": [{"world_flag": {"flag": "demon_wins", "value": True}}],
            "irreversible_facts": [{"world_flag": {"flag": "lin_dead", "value": True}}],
        }
    })


def test_backbone_must_be_an_object():
    with pytest.raises(ScenarioValidationError):
        _validate_backbone({"backbone": []})


@pytest.mark.parametrize("key", ["prohibited_predicates", "irreversible_facts"])
def test_predicate_sets_must_be_lists(key):
    with pytest.raises(ScenarioValidationError):
        _validate_backbone({"backbone": {key: {"world_flag": {"flag": "x"}}}})


@pytest.mark.parametrize("key", ["prohibited_predicates", "irreversible_facts"])
def test_each_entry_must_be_a_single_key_condition_expression(key):
    for bad in ({}, {"a": 1, "b": 2}, "always", 3):
        with pytest.raises(ScenarioValidationError):
            _validate_backbone({"backbone": {key: [bad]}})


def test_valid_nested_deterministic_backbone_passes():
    _validate_backbone({
        "backbone": {
            "prohibited_predicates": [
                {"all": [{"world_flag": {"flag": "a"}}, {"not": {"event_triggered": {"event_id": "e"}}}]},
            ]
        }
    })


@pytest.mark.parametrize("key", ["prohibited_predicates", "irreversible_facts"])
def test_nondeterministic_predicate_is_rejected(key):
    # random_chance is a coin flip — a single dry evaluation can't be a HARD gate, so
    # it must be rejected at load (else the gate passes at random, not fail-closed).
    with pytest.raises(ScenarioValidationError):
        _validate_backbone({"backbone": {key: [{"random_chance": {"chance": 0.5}}]}})


def test_nested_nondeterministic_predicate_is_rejected():
    with pytest.raises(ScenarioValidationError):
        _validate_backbone({"backbone": {"prohibited_predicates": [{"any": [{"random_chance": {"chance": 0.5}}]}]}})


def test_unknown_or_mod_predicate_is_rejected():
    # mod / unknown predicates have unknown determinism at load → rejected.
    with pytest.raises(ScenarioValidationError):
        _validate_backbone({"backbone": {"prohibited_predicates": [{"some_mod_predicate": {}}]}})
