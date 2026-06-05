# ADR-011: Scenario Discovery and Per-Game Selection

Date: 2026-06-03
Status: Accepted

## Context

Before v0.5, `--scenario` was read once at server boot and `ScenarioInjectedWorld` used module-level `ACTIVE_SCENARIO`. The UI needs to choose a scenario when starting a new game, while CLI and headless workflows must continue to work.

## Decision

v0.5 scans bundled scenarios only: `config/scenarios/<id>/scenario.json`. User-installed scenarios under a data directory are deferred to v0.6.

The public query API is:

`GET /api/v1/query/scenarios`

It returns `{"ok": true, "data": {"scenarios": [...]}}`.

`--scenario` remains a CLI default. `GameStartRequest.scenario_id` can override it for that game's lifecycle:

- omitted `scenario_id`: use CLI default
- `"default"`: no scenario
- `""`: no scenario
- explicit JSON `null`: no scenario
- any other string: load that scenario id

The resolved scenario is stored on `GameSessionRuntime.active_scenario`. `ScenarioInjectedWorld.create_with_db` reads from runtime instead of the module constant. Existing module constants remain for CLI default and legacy boot behavior.

## Consequences

Scenario selection moves from boot-time-only to per-new-game-call without introducing mid-game scenario switching. Reset/init flows may start a new world with a different selected scenario, but v0.5 does not activate or deactivate scenarios inside an existing world.

Save/load consistency now compares saves against `runtime.active_scenario.scenario_id` when present, or `None` for explicit no-scenario. This preserves the Milestone C decision to refuse loading a scenario save under a different active scenario.
