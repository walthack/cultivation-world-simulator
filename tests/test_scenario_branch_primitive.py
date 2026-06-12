"""v1.6 M1 — branch-point primitive.

A `branch` event is a first-class selector node: when it fires, the engine
evaluates each branch's condition in order and applies the FIRST matching
branch's effects (typically a set_var that downstream events gate on via
var_equals). No match → default_branch if present, else a runtime no-op
(never raise — that would crash the game loop; structural errors are caught
at load time instead).
"""

from __future__ import annotations

import pytest

from src.scenario.event_dispatcher import EventDispatcher
from src.scenario.event_handlers.branch_handler import handle_branch
from src.scenario.scenario_loader import EVENT_TYPES
from src.scenario.state_access import get_scenario_vars
from src.sim.simulator_engine.phases.scripted_scenario import _HANDLERS


def _state():
    return {
        "world": {"year": 1, "month": 1, "world_flags": {}},
        "scenario_runtime": {
            "scenario_id": "branch-test",
            "triggered_event_ids": [],
            "scenario_vars": {},
        },
    }


def _branch_event(branches, *, default_branch=None, flag=None):
    trigger = {"year": 1, "month": 1, "condition": {"always": {}}}
    if flag is not None:
        trigger["condition"] = {"world_flag": {"flag": flag}}
    event = {"id": "br", "type": "branch", "trigger": trigger, "branches": branches}
    if default_branch is not None:
        event["default_branch"] = default_branch
    return event


async def _dispatch(state, event):
    dispatcher = EventDispatcher([event], handlers={"branch": handle_branch})
    return await dispatcher.dispatch_month(state)


def _line(state):
    return get_scenario_vars(state).get("line")


def _set_var(value):
    return [{"type": "set_var", "name": "line", "value": value}]


# --- runtime semantics -------------------------------------------------------

@pytest.mark.asyncio
async def test_branch_is_a_registered_event_type_with_a_handler():
    assert "branch" in EVENT_TYPES
    assert _HANDLERS.get("branch") is handle_branch


@pytest.mark.asyncio
async def test_first_matching_branch_wins():
    state = _state()
    state["world"]["world_flags"] = {"a": True, "b": True}
    event = _branch_event([
        {"id": "first", "condition": {"world_flag": {"flag": "a"}}, "effects": _set_var("A")},
        {"id": "second", "condition": {"world_flag": {"flag": "b"}}, "effects": _set_var("B")},
    ])

    await _dispatch(state, event)

    assert _line(state) == "A"  # both match; order decides


@pytest.mark.asyncio
async def test_single_matching_branch_applies_its_effects():
    state = _state()
    state["world"]["world_flags"] = {"b": True}
    event = _branch_event([
        {"id": "first", "condition": {"world_flag": {"flag": "a"}}, "effects": _set_var("A")},
        {"id": "second", "condition": {"world_flag": {"flag": "b"}}, "effects": _set_var("B")},
    ])

    await _dispatch(state, event)

    assert _line(state) == "B"


@pytest.mark.asyncio
async def test_no_match_no_default_is_a_noop_not_a_crash():
    state = _state()
    event = _branch_event([
        {"id": "first", "condition": {"world_flag": {"flag": "a"}}, "effects": _set_var("A")},
    ])

    dispatched = await _dispatch(state, event)

    assert _line(state) is None  # nothing selected
    assert [e["id"] for e in dispatched] == ["br"]  # event still fired, no exception


@pytest.mark.asyncio
async def test_no_match_falls_back_to_default_branch():
    state = _state()
    event = _branch_event(
        [
            {"id": "first", "condition": {"world_flag": {"flag": "a"}}, "effects": _set_var("A")},
            {"id": "fallback", "condition": {"world_flag": {"flag": "z"}}, "effects": _set_var("Z")},
        ],
        default_branch="fallback",
    )

    await _dispatch(state, event)

    assert _line(state) == "Z"


# --- load-time structural validation ----------------------------------------

def _scenario_dir(tmp_path, events):
    import json

    scenario = {
        "schema_version": "0.2",
        "scenario_id": "branchval",
        "title": "Branch Validation",
        "version": "1.0",
        "author": "Test",
        "description": "branch validation fixture",
        "world_preset": {"preset_id": "default"},
        "initial_state": {"year": 1, "month": 1, "avatars": [], "relationships": [], "sects": [], "world_flags": {}},
    }
    d = tmp_path / "branchval"
    d.mkdir()
    (d / "scenario.json").write_text(json.dumps(scenario), encoding="utf-8")
    (d / "timeline.json").write_text(json.dumps({"schema_version": "0.2", "events": events}), encoding="utf-8")
    return d


def test_branch_event_without_branches_is_rejected(tmp_path):
    from src.scenario.scenario_loader import ScenarioValidationError, validate_scenario_dir

    events = [{"id": "br", "type": "branch", "trigger": {"year": 1, "month": 1, "condition": {"always": {}}}}]
    with pytest.raises(ScenarioValidationError):
        validate_scenario_dir(_scenario_dir(tmp_path, events))


def test_branch_default_referencing_unknown_branch_is_rejected(tmp_path):
    from src.scenario.scenario_loader import ScenarioValidationError, validate_scenario_dir

    events = [{
        "id": "br",
        "type": "branch",
        "trigger": {"year": 1, "month": 1, "condition": {"always": {}}},
        "branches": [{"id": "x", "condition": {"always": {}}, "effects": []}],
        "default_branch": "nonexistent",
    }]
    with pytest.raises(ScenarioValidationError):
        validate_scenario_dir(_scenario_dir(tmp_path, events))
