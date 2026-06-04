from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.scenario.condition_evaluator import evaluate_condition
from src.scenario.effect_applier import apply_effects
from src.scenario.event_dispatcher import EventDispatcher
from src.scenario.state import ScriptedScenarioState
from src.server.api.public_v1.command import create_public_command_router
from src.server.runtime.session import GameSessionRuntime, create_default_game_state
from src.server.services.scenario_debug import get_debug_snapshot
from src.server.services.scenario_runtime import (
    ADVANCED_RUNTIME_CONTROL_DISABLED,
    HOT_SWAP_WARNING,
    ScenarioRuntimeError,
    activate_scenario,
    deactivate_scenario,
    reload_scenario,
)


def _resolved(scenario_id: str, timeline: list[dict] | None = None, *, year: int = 1, month: int = 1):
    return SimpleNamespace(
        scenario_id=scenario_id,
        title=scenario_id,
        version="0.1",
        preset_id="default",
        timeline=list(timeline or []),
        scenario={
            "scenario_id": scenario_id,
            "title": scenario_id,
            "version": "0.1",
            "initial_state": {"year": year, "month": month},
        },
    )


def _runtime(world=None, *, advanced: bool = True):
    state = create_default_game_state()
    state["world"] = world
    runtime = GameSessionRuntime(state)
    runtime.advanced_runtime_control = advanced
    return runtime


def _world(scenario_id: str = "alpha"):
    return SimpleNamespace(
        month_stamp=1205,
        avatar_manager=SimpleNamespace(avatars={"avatar-a": object()}),
        scripted_scenario=ScriptedScenarioState(
            scenario_id=scenario_id,
            timeline=[{"id": "old", "trigger": {"year": 1, "month": 1}}],
            state={"kept": "value"},
            triggered_events={"old"},
        ),
    )


@pytest.mark.asyncio
async def test_activate_reset_mode_recreates_world():
    runtime = _runtime(_world("alpha"))
    created_world = _world("beta")

    async def fake_start(req):
        runtime.state["world"] = created_world
        runtime.active_scenario = _resolved(req.scenario_id)
        return {"status": "ok"}

    class Request(SimpleNamespace):
        pass

    result = await activate_scenario(
        runtime,
        "beta",
        "reset",
        run_start_game=fake_start,
        start_request_factory=lambda scenario_id: Request(scenario_id=scenario_id),
    )

    assert result == {"ok": True}
    assert runtime.get("world") is created_world
    assert runtime.active_scenario.scenario_id == "beta"


@pytest.mark.asyncio
async def test_activate_hot_swap_keeps_month_stamp(monkeypatch):
    world = _world("alpha")
    runtime = _runtime(world)
    monkeypatch.setattr("src.server.services.scenario_runtime.scenario_loader.load", lambda scenario_id: _resolved(scenario_id))

    before = world.month_stamp
    result = await activate_scenario(runtime, "beta", "hot-swap")

    assert result["ok"] is True
    assert world.month_stamp == before
    assert world.scripted_scenario.scenario_id == "beta"
    assert world.scripted_scenario.state == {}
    assert world.scripted_scenario.triggered_events == set()


def test_deactivate_strips_scenario_keeps_avatars():
    world = _world("alpha")
    avatars = world.avatar_manager.avatars
    runtime = _runtime(world)

    result = deactivate_scenario(runtime)

    assert result == {"ok": True}
    assert world.scripted_scenario is None
    assert world.avatar_manager.avatars is avatars
    assert "avatar-a" in world.avatar_manager.avatars


def test_reload_preserves_state_and_triggered_events(monkeypatch):
    world = _world("alpha")
    world.scripted_scenario.state["runtime_var"] = 7
    world.scripted_scenario.triggered_events.add("already-fired")
    world.scripted_scenario.dispatch_log.append({"month_stamp": "Y1M1", "event_id": "old", "fired": True})
    runtime = _runtime(world)
    monkeypatch.setattr(
        "src.server.services.scenario_runtime.scenario_loader.load",
        lambda scenario_id: _resolved(scenario_id, [{"id": "new", "trigger": {"year": 2, "month": 1}}]),
    )

    result = reload_scenario(runtime)

    assert result == {"ok": True}
    assert world.scripted_scenario.timeline == [{"id": "new", "trigger": {"year": 2, "month": 1}}]
    assert world.scripted_scenario.state["runtime_var"] == 7
    assert world.scripted_scenario.triggered_events == {"old", "already-fired"}
    assert world.scripted_scenario.dispatch_log == [{"month_stamp": "Y1M1", "event_id": "old", "fired": True}]


def test_set_var_writes_to_state():
    state = {"scenario_runtime": {}}

    apply_effects(state, [{"type": "set_var", "name": "phase", "value": "opened"}])

    assert state["scenario_runtime"]["phase"] == "opened"


def test_var_equals_reads_from_state():
    state = {"scenario_runtime": {"phase": "opened"}}

    assert evaluate_condition(state, {"var_equals": {"name": "phase", "value": "opened"}}) is True
    assert evaluate_condition(state, {"var_equals": {"name": "phase", "value": "closed"}}) is False


def test_advanced_mode_gate_blocks_activate_when_disabled():
    app = FastAPI()

    async def blocked_activate(**_kwargs):
        raise ScenarioRuntimeError(ADVANCED_RUNTIME_CONTROL_DISABLED)

    async def noop_async(*_args, **_kwargs):
        return {}

    def noop(*_args, **_kwargs):
        return {}

    app.include_router(
        create_public_command_router(
            run_start_game=noop_async,
            run_reinit_game=noop_async,
            run_reset_game=noop_async,
            trigger_process_shutdown=noop,
            run_pause_game=noop_async,
            run_resume_game=noop_async,
            run_set_long_term_objective=noop_async,
            run_clear_long_term_objective=noop_async,
            run_create_avatar=noop_async,
            run_delete_avatar=noop_async,
            run_update_avatar_adjustment=noop_async,
            run_update_avatar_portrait=noop_async,
            run_generate_custom_content=noop_async,
            run_create_custom_content=noop,
            run_set_phenomenon=noop_async,
            run_bulk_import_world=noop_async,
            run_cleanup_events=noop_async,
            run_save_game=noop,
            run_delete_save=noop,
            run_load_game=noop_async,
            run_start_roleplay=noop_async,
            run_stop_roleplay=noop_async,
            run_submit_roleplay_decision=noop_async,
            run_submit_roleplay_choice=noop_async,
            run_send_roleplay_conversation=noop_async,
            run_end_roleplay_conversation=noop_async,
            run_activate_scenario=blocked_activate,
        )
    )

    response = TestClient(app).post(
        "/api/v1/command/scenario/activate",
        json={"scenario_id": "beta", "mode": "hot-swap"},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": False, "error": ADVANCED_RUNTIME_CONTROL_DISABLED}


@pytest.mark.asyncio
async def test_debug_snapshot_returns_vars_triggered_dispatch_log():
    world = _world("alpha")
    world.scripted_scenario.state["phase"] = "opened"
    world.scripted_scenario.triggered_events.add("intro")
    dispatcher = EventDispatcher(
        [
            {"id": "intro", "trigger": {"year": 1, "month": 1}},
            {"id": "future", "trigger": {"year": 2, "month": 1}},
        ]
    )
    state = {
        "world": {"year": 1, "month": 1},
        "scenario_runtime": {
            "triggered_event_ids": [],
            "dispatch_log": world.scripted_scenario.dispatch_log,
        },
    }

    await dispatcher.dispatch_month(state)
    world.scripted_scenario.dispatch_log = state["scenario_runtime"]["dispatch_log"]
    snapshot = get_debug_snapshot(world)

    assert snapshot["state"]["phase"] == "opened"
    assert "intro" in snapshot["triggered_events"]
    assert snapshot["dispatch_log"][-1]["event_id"] == "future"
    assert snapshot["dispatch_log"][-1]["fired"] is False


@pytest.mark.asyncio
async def test_hot_swap_response_includes_verbatim_warning(monkeypatch):
    world = _world("alpha")
    runtime = _runtime(world)
    monkeypatch.setattr("src.server.services.scenario_runtime.scenario_loader.load", lambda scenario_id: _resolved(scenario_id))

    response = await activate_scenario(runtime, "beta", "hot-swap")

    assert response["warning"] == HOT_SWAP_WARNING
    assert response["warning"] == "Hot-swap does not re-anchor time. Events scheduled before the current world time will not fire."
