# ADR-006: Scenario Stage 2d Server Integration

## Status

Accepted for Stage 2d D-d2.

## Context

Stage 2c made scenario timelines sensitive to the controlled avatar, but the scenario engine was still only exercised through in-process scenario tests. Stage 2d D-d2 needs server boot integration for `--scenario <id>` and a simulator hook that can consume injected scenario data without turning the scenario engine into a long-lived runtime owner.

The signed rev 2 decision moved live scenario state to `World`. Scenario state must not live on `GameSessionRuntime`, and the scenario engine should leave the boot critical path after injecting data.

## Decision

Add `world.scripted_scenario`, an in-memory `ScriptedScenarioState` containing the scenario id, timeline, mutable state, and triggered event ids. Server boot loads the requested scenario id and injects that state into the freshly created world. A missing scenario id is not caught; boot fails instead of silently falling back.

Add simulator phase 12.5, `scripted_scenario_tick`, immediately after passive effects and before autonomous custom creation. This position lets ordinary world upkeep finish first while scripted scenario events still run before random minor content for the same month.

When no scenario is active, `world.scripted_scenario is None` and phase 12.5 returns an empty list. This preserves default-game behavior and keeps the phase always present in the simulator sequence.

Roleplay remains the source of the currently controlled avatar. The bridge writes `world.scripted_scenario.state["controlled_avatar"]` on start, on mid-session controlled-avatar writes, and clears it on stop. Scenario predicates can then remain data-driven and independent from roleplay session internals.

## Consequences

Scenario data is owned by the world layer. The evaluator phase is stateless apart from reading and writing `world.scripted_scenario`, including its `triggered_events` set.

The scenario engine does not add API endpoints, does not support runtime scenario switching, and does not write scenario state into save files in D-d2. Persistence of `ScriptedScenarioState` is deferred to v0.3, when save/load semantics can be designed with migration rules.

The roleplay bridge has three required sync points because player control can enter roleplay, move into a choice or conversation wait, and exit roleplay. Keeping all writes mirrored avoids stale perspective filtering for timeline events.

## Alternatives

One alternative was to store a scenario dispatcher or resolved scenario state on runtime. Rev 2 rejects that because it makes the scenario engine a runtime subsystem instead of a world injection layer.

Another alternative was to skip the simulator phase when no scenario is active. A permanent noop phase is simpler to reason about and makes the phase order explicit.
