"""Cross-schema import verification.

Goal (v1.5): prove that importing scenarios authored against *different* schema
versions all take effect end-to-end — load → dispatch opening month → the
opening event's effect actually lands in world state.

Covered installed scenarios and their declared schemas:
  - sample : scenario 0.1 / timeline 0.1, default (修真) progression
  - liuchao: scenario 1.2 / timeline 0.2, historical progression profile
  - sanguo : scenario 1.2 / timeline 0.2, historical progression profile
"""

from __future__ import annotations

import pytest

from src.scenario.event_dispatcher import EventDispatcher
from src.scenario.event_handlers.main_event_handler import handle_main_event
from src.scenario.event_handlers.side_event_handler import handle_side_event
from src.scenario.scenario_loader import EVENT_TYPES, _is_v02, load
from src.sim.simulator_engine.phases.scripted_scenario import _HANDLERS


INSTALLED_SCENARIOS = ("sample", "liuchao", "sanguo")


def _first_set_flag(event: dict) -> str | None:
    for effect in event.get("effects", []) or []:
        if effect.get("type") == "set_flag":
            return effect["flag"]
    return None


def _minimal_state(scenario) -> dict:
    """Build the smallest state the dispatcher needs for opening events.

    Opening events across all scenarios use `always` / no condition, so no
    player or controlled-avatar wiring is required.
    """
    initial = scenario.scenario["initial_state"]
    return {
        "world": {
            "year": initial["year"],
            "month": initial["month"],
            "world_flags": dict(initial.get("world_flags", {})),
        },
        "scenario_runtime": {
            "scenario_id": scenario.scenario_id,
            "triggered_event_ids": [],
            "event_outcomes": {},
        },
    }


@pytest.mark.parametrize("scenario_id", INSTALLED_SCENARIOS)
def test_installed_scenario_loads_across_schema_versions(scenario_id):
    scenario = load(scenario_id)

    assert scenario.scenario_id == scenario_id
    assert scenario.timeline, f"{scenario_id} imported an empty timeline"


@pytest.mark.parametrize("scenario_id", INSTALLED_SCENARIOS)
@pytest.mark.asyncio
async def test_installed_scenario_opening_event_takes_effect(scenario_id):
    scenario = load(scenario_id)
    opening = scenario.timeline[0]
    flag = _first_set_flag(opening)
    assert flag, f"{scenario_id} opening event {opening.get('id')} has no set_flag to verify"

    state = _minimal_state(scenario)
    dispatcher = EventDispatcher(
        scenario.timeline,
        handlers={"main": handle_main_event, "side_event": handle_side_event},
    )

    dispatched = await dispatcher.dispatch_month(state)

    # The opening event fired this month...
    assert opening["id"] in [event["id"] for event in dispatched]
    assert opening["id"] in state["scenario_runtime"]["triggered_event_ids"]
    # ...and its effect actually landed in world state.
    assert state["world"]["world_flags"].get(flag) is True


def test_every_recognized_event_type_has_a_production_handler():
    """An event type the loader accepts but the dispatcher has no handler for
    would dispatch silently without applying effects (see EventDispatcher: a
    missing handler still marks the event fired). Guard the loader↔dispatcher
    contract so a recognized type can never become a silent no-op."""
    unhandled = EVENT_TYPES - set(_HANDLERS)

    assert not unhandled, f"recognized event types with no production handler: {sorted(unhandled)}"


def test_v1_2_schema_runs_reference_validation():
    """schema 1.2 is the newest version and must get the v0.2-family reference
    validation (race_id/root_id/region/etc.); regression guard for the
    _is_v02 gap that previously let 1.2 import unvalidated."""
    assert _is_v02({"schema_version": "1.2"}) is True
