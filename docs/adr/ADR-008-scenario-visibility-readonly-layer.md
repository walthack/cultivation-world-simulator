# ADR-008: Scenario Visibility Read-Only Layer

## Status

Accepted for Milestone B.

## Context

Stage 2d can boot a resolved scenario into the live runtime and attach `ScriptedScenarioState` to `world.scripted_scenario`. The player still has no visible confirmation that a scenario is active, no way to inspect the scenario background, and no UI surface for timeline progress. That makes scenario boot look identical to the default game even when authored timeline events are firing.

Milestone B is intentionally a visibility milestone. Avatar injection, relation injection, scripted-scenario save/load persistence, and mutation endpoints remain Milestone C or later work. The visibility layer must read existing runtime state without changing dispatcher semantics.

## Decision

Add `GET /api/v1/query/scenario/status` as a public v1 query endpoint. The route returns `{ "active": false }` when no scenario is attached, and returns the resolved scenario metadata plus the runtime timeline status when a scenario is active. The endpoint reads `world.scripted_scenario`, the resolved active scenario object, `triggered_events`, scenario state, and world flags. It does not mutate the world and does not call the dispatcher.

The DTO uses an explicit `active: boolean` wrapper instead of nullable top-level fields. That keeps the default-game response small and unambiguous, while letting the active response require `scenario_id`, `title`, `version`, `world_background`, `preset_id`, `timeline`, and `world_flags`. Timeline events include a `triggered` flag per authored event so the frontend can group fired and upcoming entries without reconstructing runtime state.

The frontend stores the response in a dedicated Pinia `scenario` store. This mirrors existing CWS stores that cache query responses and expose an explicit refresh action. The store refreshes after world initialization and on each tick, and the socket router also refreshes on a future `scenario_event` message if the backend emits one later.

The badge is mounted in the App-level top control cluster. This keeps it visible during gameplay without changing the default status bar contract, and it disappears entirely when no scenario is active. Clicking the badge opens an App-level modal using the same `show`/`v-model:show` convention as existing overview modals.

The modal displays resolved scenario metadata, escaped plain-text world background, triggered events, untriggered events, and the controlled avatar marker when present. The timeline is read-only and has no controls.

## Consequences

Default-game UI remains unchanged because inactive status renders no badge and the modal is only mounted after a badge click.

Scenario progress becomes visible as soon as the world initializes and stays current after simulator ticks. Refreshing every tick is acceptable for Milestone B because the payload is small and avoids depending on a new backend event channel.

The frontend can safely render scenario prose with Vue text interpolation. Authored `world_background` is not inserted as HTML.

The API shape leaves room for later tracked trigger timestamps. `triggered_month_stamp` is optional and only present when runtime state already records it; the visibility layer does not fabricate values.

## Alternatives

One alternative was to add a mutation-oriented scenario control panel. That was rejected because Milestone B is a visibility layer and mutation semantics belong to later scenario-engine milestones.

Another alternative was to put scenario fields into the existing world-state payload. That would make every map/state refresh carry scenario-specific data, even for default games. A focused query endpoint keeps the scenario contract isolated and easier for external agents to consume.

A third alternative was to require a backend socket message for every scenario event and refresh only from that message. The current backend does not expose a dedicated scenario-event socket contract, so the store refreshes on ticks and supports a future `scenario_event` message when it exists.
