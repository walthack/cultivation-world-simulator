# ADR-017: Scenario Runtime Debugging

Date: 2026-06-04

## Status

Accepted.

## Context

Scenario authors and advanced operators need to inspect scenario runtime internals during play without adding creator workflow changes or dangerous mutation shortcuts.

## Decision

The debug endpoint is `GET /api/v1/query/scenario/debug`. It is gated by `advanced_runtime_control` and returns:

- `state`: current `scripted_scenario.state` variables.
- `triggered_events`: current triggered event ids.
- `dispatch_log`: the last 50 dispatch diagnostics with `month_stamp`, `event_id`, `fired`, and optional `reason`.

The dispatch log is a transient ring buffer on `ScriptedScenarioState`. It is not written to save files, so v0.8 does not change save/load schema.

The frontend renders debugging inside `ScenarioOverviewModal` as a Debug tab visible only when advanced runtime control is enabled.

## Consequences

Runtime debugging is read-only in v0.8. There is no force-fire button, because that would add a new mutation path and could bypass normal scenario semantics.
