# ADR-024: Scenario World Generation Control

Date: 2026-06-07

## Status

Accepted for v1.1.

## Context

Scenario v1.0 and v1.0.1 injected scripted avatars, relationships, and timelines, but the default random world generation still ran on top of scenario content. A scenario such as 六朝 therefore started with scripted characters alongside the normal random NPC and sect fill, making the world feel predominantly procedural rather than authored.

Master playtest feedback on 2026-06-07 identified this as a gap in the scenario engine's promise to import a pre-defined world. The v1.0.1 random scatter fallback fixed visual stacking at `(0, 0)`, but it did not let scenario authors control how much default randomness should exist.

## Decision

Scenario schema v1.1 introduces `initial_state.generation_profile` with `random_npc_count`, `random_sect_count`, and `use_scripted_only`. When a scenario is active, these values override the runtime new-game defaults for random NPC and sect generation. If the profile is omitted, the existing settings-driven behavior remains unchanged.

Scenario avatars also support placement fields:

- `pos`: explicit map coordinates.
- `region_id`: choose a random tile inside a known runtime region.

Placement priority is `pos` first, then `region_id`, then the v1.0.1 random fallback. The loader validates schema shape and simple value constraints; map bounds and region existence are validated during injection because only the built world map knows those runtime details.

## Alternatives Considered

- Replace settings defaults entirely whenever any scenario is active. This was too blunt because some scenarios want scripted content as light seasoning on a procedural world.
- Add only per-avatar count overrides without a profile block. This could not express a fully scripted world.
- Encode strict and loose variants in scenario ids, such as `liuchao-strict` and `liuchao-loose`. This would multiply scenario ids and make fallback behavior unclear.

## Consequences

Existing schema v0.1 scenarios continue to load and preserve v1.0 behavior when they omit the new profile.

No-scenario games remain settings-driven and do not enter the scenario generation control path.

Scenario authors gain a single explicit control surface for pure scripted worlds, lightly mixed worlds, and mostly procedural worlds with authored anchors.

Bundled `liuchao` and `sanguo` scenarios now serve as examples of intentional generation profiles. Follow-up authoring UI can expose the same fields without changing the runtime contract.
