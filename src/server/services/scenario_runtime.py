from __future__ import annotations

from typing import Any, Awaitable, Callable, Literal

from pydantic import BaseModel

from src.scenario import scenario_loader
from src.scenario.source_resolver import set_active_scenario_source
from src.scenario.state import ScriptedScenarioState


HOT_SWAP_WARNING = "Hot-swap does not re-anchor time. Events scheduled before the current world time will not fire."
ADVANCED_RUNTIME_CONTROL_DISABLED = "Advanced runtime control disabled in settings"
ScenarioActivateMode = Literal["reset", "hot-swap"]


class ScenarioRuntimeError(ValueError):
    pass


def advanced_runtime_control_enabled(runtime: Any) -> bool:
    return bool(getattr(runtime, "advanced_runtime_control", False))


def ensure_advanced_runtime_control(runtime: Any) -> None:
    if not advanced_runtime_control_enabled(runtime):
        raise ScenarioRuntimeError(ADVANCED_RUNTIME_CONTROL_DISABLED)


def _world(runtime: Any) -> Any:
    world = runtime.get("world") if hasattr(runtime, "get") else None
    if world is None:
        raise ScenarioRuntimeError("No running world")
    return world


def _replace_active_scenario(runtime: Any, resolved: Any | None) -> None:
    if hasattr(runtime, "active_scenario"):
        runtime.active_scenario = resolved
    if hasattr(runtime, "active_scenario_explicit"):
        runtime.active_scenario_explicit = True
    if hasattr(runtime, "state") and isinstance(runtime.state, dict):
        runtime.state["active_scenario"] = getattr(resolved, "scenario_id", None)
    set_active_scenario_source(resolved, explicit=resolved is not None)


async def activate_scenario(
    runtime: Any,
    scenario_id: str,
    mode: ScenarioActivateMode,
    *,
    run_start_game: Callable[[BaseModel], Awaitable[dict] | dict] | None = None,
    start_request_factory: Callable[[str], BaseModel] | None = None,
) -> dict[str, Any]:
    ensure_advanced_runtime_control(runtime)
    normalized_mode = str(mode or "reset")
    if normalized_mode not in {"reset", "hot-swap"}:
        raise ScenarioRuntimeError(f"Unsupported scenario activation mode: {mode}")

    if normalized_mode == "reset":
        if run_start_game is None or start_request_factory is None:
            raise ScenarioRuntimeError("Reset activation requires a start game callback")
        result = run_start_game(start_request_factory(scenario_id))
        if hasattr(result, "__await__"):
            await result
        return {"ok": True}

    resolved = scenario_loader.load(str(scenario_id))
    world = _world(runtime)
    month_stamp = world.month_stamp
    world.scripted_scenario = ScriptedScenarioState(
        scenario_id=resolved.scenario_id,
        timeline=list(resolved.timeline or []),
        state={},
        triggered_events=set(),
    )
    world.month_stamp = month_stamp
    _replace_active_scenario(runtime, resolved)
    return {"ok": True, "warning": HOT_SWAP_WARNING}


def deactivate_scenario(runtime: Any) -> dict[str, Any]:
    ensure_advanced_runtime_control(runtime)
    world = _world(runtime)
    world.scripted_scenario = None
    _replace_active_scenario(runtime, None)
    return {"ok": True}


def reload_scenario(runtime: Any) -> dict[str, Any]:
    ensure_advanced_runtime_control(runtime)
    world = _world(runtime)
    scripted_scenario = getattr(world, "scripted_scenario", None)
    if scripted_scenario is None:
        raise ScenarioRuntimeError("No active scenario")

    preserved_state = dict(getattr(scripted_scenario, "state", {}) or {})
    preserved_triggered = set(getattr(scripted_scenario, "triggered_events", set()) or set())
    preserved_dispatch_log = list(getattr(scripted_scenario, "dispatch_log", []) or [])
    resolved = scenario_loader.load(str(scripted_scenario.scenario_id))
    world.scripted_scenario = ScriptedScenarioState(
        scenario_id=resolved.scenario_id,
        timeline=list(resolved.timeline or []),
        state=preserved_state,
        triggered_events=preserved_triggered,
        dispatch_log=preserved_dispatch_log[-50:],
    )
    _replace_active_scenario(runtime, resolved)
    return {"ok": True}
