# ADR-007: Scenario Start-Time Injection

## Status

Accepted for Stage 2d D-d2 bugfix.

## Context

Stage 2d D-d2 injects an active scenario into the newly created world, but world creation still receives the default CWS start time from `static/config.yml`: `world.start_year = 100` and January. Scenario data already declares its intended opening date in `initial_state.year` and `initial_state.month`; for example, `liuchao` starts at year 1 month 1 and `sanguo` starts at year 208 month 1.

The scenario dispatcher intentionally matches timeline triggers by exact year and month. When the live runtime starts an active scenario at year 100, timeline events anchored to year 1 or year 208 are unreachable unless tests manually mutate state before dispatch. That hides the live-runtime bug and makes the scenario engine appear wired while its data cannot fire in normal play.

## Decision

When `ACTIVE_SCENARIO` is present, `ScenarioInjectedWorld.create_with_db` reads `ACTIVE_SCENARIO.scenario["initial_state"]["year"]` and `["month"]` before calling `World.create_with_db`. If both values are present and valid, the wrapper replaces the `month_stamp` keyword argument and the `start_year` keyword argument with the scenario start date. If either field is missing or invalid, world creation keeps the existing CWS defaults supplied by the init flow.

This is Approach 1, the pre-create-world peek. It makes the scenario start time the value consumed by `World.create_with_db`, tournament initialization, and the dynasty emperor generation that happens immediately after world creation in the init flow.

Option A is kept: scenario `initial_state.year/month` override the CWS default while a scenario is active. Re-anchoring timeline data to year 100 was rejected because it would make scenario files follow a default-game implementation detail instead of their own authored chronology.

Dispatcher semantics remain exact equality. The bug is not that timeline matching is too strict; the bug is that live runtime boot used the wrong current year and month. Keeping `==` preserves deterministic one-month triggers and existing dispatcher contract tests.

## Consequences

`liuchao` starts at year 1 month 1 in live runtime, so `liuchao-opening` is reachable without manual state mutation. `sanguo` starts at year 208 month 1 under the same wrapper path.

Default no-scenario boot remains unchanged because the wrapper only rewrites start time when an active scenario is loaded and has valid initial-state fields.

The scenario injector remains responsible for attaching `ScriptedScenarioState` to the world. It does not mutate `world.month_stamp` after creation, does not inject scenario avatars into `world.avatar_manager`, and does not alter save/load behavior.

## Alternatives

One alternative was to mutate `world.month_stamp` inside `inject_scenario_into_world`. That would update the visible world date after creation, but it risks leaving world subsystems that already consumed the original date out of sync. In particular, the init flow generates the current emperor from `world.month_stamp` immediately after world creation, so post-hoc mutation would need additional repair logic.

Another alternative was to retarget scenario timeline data to the CWS default year 100. That would make current data pass with no engine fix, but it would erase scenario-specific chronology and repeat the same problem for scenarios such as `sanguo` that naturally start in a different era.

A third alternative was to change dispatcher matching from exact equality to a range or catch-up semantic. That would expand event firing behavior beyond the D-d2 bugfix and could make old missed events fire at later dates. Stage 2d keeps the dispatcher contract narrow and deterministic.
