"""v1.6 step B — first-class storyline + engine-managed mutual exclusion.

A `branch` (step A) selects one path; step B makes that path a named
*storyline*. Events tagged `storyline: X` only dispatch while X is active;
a branch activates exactly one sibling storyline, so the others never fire
— engine-managed one-way-tree mutual exclusion, no manual blocks_events.
"""

from __future__ import annotations

import pytest

from src.scenario.event_dispatcher import EventDispatcher
from src.scenario.event_handlers.branch_handler import handle_branch
from src.scenario.event_handlers.side_event_handler import handle_side_event
from src.scenario.effect_applier import apply_effects
from src.scenario.state_access import get_active_storylines


def _state(**flags):
    return {
        "world": {"year": 1, "month": 1, "world_flags": dict(flags)},
        "scenario_runtime": {"scenario_id": "sl", "triggered_event_ids": []},
    }


def _handlers():
    return {"branch": handle_branch, "side_event": handle_side_event}


def _tagged(event_id, storyline, flag="seen"):
    return {
        "id": event_id,
        "type": "side_event",
        "storyline": storyline,
        "trigger": {"year": 1, "month": 1, "condition": {"always": {}}},
        "effects": [{"type": "set_flag", "flag": flag}],
    }


# --- effect + accessor -------------------------------------------------------

def test_activate_storyline_effect_adds_to_active_set():
    state = _state()
    apply_effects(state, [{"type": "activate_storyline", "storyline": "north"}])

    assert "north" in get_active_storylines(state)


# --- dispatch gating ---------------------------------------------------------

@pytest.mark.asyncio
async def test_event_tagged_with_inactive_storyline_does_not_fire():
    state = _state()
    dispatcher = EventDispatcher([_tagged("e", "north")], handlers=_handlers())

    dispatched = await dispatcher.dispatch_month(state)

    assert dispatched == []
    assert state["world"]["world_flags"].get("seen") is None


@pytest.mark.asyncio
async def test_event_tagged_with_active_storyline_fires():
    state = _state()
    apply_effects(state, [{"type": "activate_storyline", "storyline": "north"}])
    dispatcher = EventDispatcher([_tagged("e", "north")], handlers=_handlers())

    dispatched = await dispatcher.dispatch_month(state)

    assert [e["id"] for e in dispatched] == ["e"]
    assert state["world"]["world_flags"]["seen"] is True


@pytest.mark.asyncio
async def test_untagged_trunk_event_always_fires():
    state = _state()
    trunk = {"id": "trunk", "type": "side_event",
             "trigger": {"year": 1, "month": 1, "condition": {"always": {}}},
             "effects": [{"type": "set_flag", "flag": "trunk_seen"}]}
    dispatcher = EventDispatcher([trunk], handlers=_handlers())

    await dispatcher.dispatch_month(state)

    assert state["world"]["world_flags"]["trunk_seen"] is True


@pytest.mark.asyncio
async def test_branch_activates_one_storyline_others_stay_suppressed():
    """One-way tree: branch picks the 'hardened' line; only its events fire."""
    state = _state(loyal=True)
    timeline = [
        {
            "id": "fork",
            "type": "branch",
            "trigger": {"year": 1, "month": 1, "condition": {"always": {}}},
            "branches": [
                {"id": "hardened", "condition": {"world_flag": {"flag": "loyal"}},
                 "effects": [{"type": "activate_storyline", "storyline": "hardened"}]},
                {"id": "channel", "condition": {"world_flag": {"flag": "hedged"}},
                 "effects": [{"type": "activate_storyline", "storyline": "channel"}]},
            ],
        },
        _tagged("hardened-beat", "hardened", flag="hardened_seen"),
        _tagged("channel-beat", "channel", flag="channel_seen"),
    ]
    dispatcher = EventDispatcher(timeline, handlers=_handlers())

    dispatched = await dispatcher.dispatch_month(state)

    ids = [e["id"] for e in dispatched]
    assert "hardened-beat" in ids
    assert "channel-beat" not in ids  # sibling line never activated
    assert state["world"]["world_flags"].get("hardened_seen") is True
    assert state["world"]["world_flags"].get("channel_seen") is None


# --- load-time structural validation ----------------------------------------

def _scenario_dir(tmp_path, events):
    import json

    scenario = {
        "schema_version": "0.2", "scenario_id": "slval", "title": "SL",
        "version": "1.0", "author": "T", "description": "storyline fixture",
        "world_preset": {"preset_id": "default"},
        "initial_state": {"year": 1, "month": 1, "avatars": [], "relationships": [], "sects": [], "world_flags": {}},
    }
    d = tmp_path / "slval"
    d.mkdir()
    (d / "scenario.json").write_text(json.dumps(scenario), encoding="utf-8")
    (d / "timeline.json").write_text(json.dumps({"schema_version": "0.2", "events": events}), encoding="utf-8")
    return d


def test_storyline_tagged_event_with_no_activator_is_rejected(tmp_path):
    """An event on a storyline that nothing can activate is unreachable."""
    from src.scenario.scenario_loader import ScenarioValidationError, validate_scenario_dir

    events = [_tagged("orphan", "ghostline")]  # no activate_storyline anywhere
    with pytest.raises(ScenarioValidationError):
        validate_scenario_dir(_scenario_dir(tmp_path, events))


def test_storyline_with_activator_is_accepted(tmp_path):
    from src.scenario.scenario_loader import validate_scenario_dir

    events = [
        {"id": "fork", "type": "branch",
         "trigger": {"year": 1, "month": 1, "condition": {"always": {}}},
         "branches": [{"id": "g", "condition": {"always": {}},
                       "effects": [{"type": "activate_storyline", "storyline": "ghostline"}]}]},
        _tagged("beat", "ghostline"),
    ]
    result = validate_scenario_dir(_scenario_dir(tmp_path, events))
    assert result.scenario_id == "slval"
