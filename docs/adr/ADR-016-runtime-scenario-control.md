# ADR-016: Runtime Scenario Control

Date: 2026-06-04

## Status

Accepted.

## Context

Scenario v0.8 needs runtime controls for a running game: activate another scenario, deactivate the active scenario, and reload the active scenario from disk. These controls are powerful enough to disrupt a game, so they are hidden behind the application setting `advanced_runtime_control`, which defaults to `false`.

## Decision

Activation supports two modes:

- `reset`: delegates to the existing game start flow with the requested `scenario_id`.
- `hot-swap`: replaces `world.scripted_scenario` in place with a fresh `ScriptedScenarioState` for the requested scenario. It clears scenario state and triggered events, but leaves `world.month_stamp` unchanged.

Hot-swap does not re-anchor time. Events scheduled before the current world time will not fire.

Deactivate sets `world.scripted_scenario = None`. Existing avatars remain in the world.

Reload reads the active scenario from disk again, refreshes timeline and metadata, and preserves runtime state plus `triggered_events`.

All runtime-control command endpoints return `{ok: false, error: "Advanced runtime control disabled in settings"}` when the advanced setting is off.

## Consequences

Hot-swap is predictable and does not mutate authored timeline data. Users who need a fresh time anchor should use reset activation.

Deactivate preserves world history and avoids deleting avatars that may already be referenced by events, relationships, or saves.
