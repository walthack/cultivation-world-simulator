# ADR-0001: Scenario DSL Naming Alignment

## Status

Accepted for Stage 2a Batch A.

## Context

The external Schema v0.1 document listed predicate and effect names before Stage 1 implementation settled. Stage 1 D7 implemented and tested a runtime DSL with 13 required predicates plus `event_triggered`, and 17 effect types. The implemented names are already used by `config/scenarios/liuchao/timeline.json`, `tests/test_scenario_condition_evaluator.py`, `tests/test_scenario_effect_applier.py`, and the scenario event handlers.

Batch A v0.2 must freeze one canonical naming set without expanding scope or forking the choice/event system.

## Decision

Prefer the Stage 1 implementation names as canonical v0.2 names.

Canonical predicate names are frozen in `src/scenario/schema_constants.py` as `ScenarioPredicate` / `CANONICAL_PREDICATES`.

Canonical effect names are frozen in `src/scenario/schema_constants.py` as `ScenarioEffectType` / `CANONICAL_EFFECT_TYPES`.

The older v0.1 document names are recorded as migration drift only. They are not automatically accepted aliases in Batch A because accepting both sets would create two public contracts during the migration period.

## Predicate drift list

| v0.1 document name | v0.2 canonical / disposition |
|---|---|
| `avatar_alive` | `npc_alive` |
| `avatar_dead` | `not npc_alive` |
| `avatar_at_sect` | Not in Batch A canonical set |
| `avatar_realm_at_least` | `npc_realm` |
| `avatar_age_at_least` | Future npc/player stat extension |
| `sect_exists` | Not in Batch A canonical set |
| `sect_leader_is` | Not in Batch A canonical set |
| `flag_set` | `world_flag` |
| `flag_unset` | `world_flag` with `value: false` |
| `relation_at_least` | `npc_relation` or `player_relation` |
| `event_triggered` | `event_triggered` |
| `event_outcome_was` | Not in Batch A canonical set |
| `controlled_avatar_is` | Not in Batch A canonical set |

## Effect drift list

| v0.1 document name | v0.2 canonical / disposition |
|---|---|
| `set_flag` | `set_flag` |
| `unset_flag` | `clear_flag` |
| `spawn_avatar` | `character_introduction` handler path, future `npc_spawn` effect if needed |
| `delete_avatar` | `npc_die` |
| `set_avatar_field` | `set_stat` for player stats; broader npc field mutation is future scope |
| `change_avatar_sect` | `npc_join` / `npc_leave` for Stage 1 scope |
| `set_avatar_realm` | `npc_set_realm` |
| `grant_goldfinger` | Future goldfinger effect |
| `set_relation` | `npc_set_relation` |
| `delta_relation` | `relation_change` |
| `add_sect_member` | `npc_join` |
| `remove_sect_member` | `npc_leave` |
| `change_sect_leader` | Future sect effect |
| `set_world_field` | `set_flag` / `clear_flag` for flag scope |
| `apply_to_region` | Future region effect |
| `economy_event` | `economy_event` no-op placeholder |
| `inject_narrative` | Future narrative effect |

## Consequences

Schema v0.2 examples and tests should use implementation names only. Existing v0.1 scenarios remain backward-compatible as data files, but old DSL names are not silently translated. If a future migration tool is needed, it should consume the drift maps from `schema_constants.py` and rewrite JSON explicitly.
