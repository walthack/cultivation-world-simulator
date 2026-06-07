# ADR-025: Scenario Generation Source Control

## Status

Accepted for v1.2.

## Context

v1.1 lets scenarios control generated population counts and scripted avatar placement, but procedurally generated NPCs still used CWS default pools for names, personas, weapons, techniques, and related generation data. That made a scenario look partially imported: the scripted backbone matched the scenario, while random fill-in content still felt like the default sandbox.

The existing preset directory structure already provides reusable scenario-flavored pool files under `config/presets/<preset_id>/`, but missing files previously fell back silently. Scenario authors had no way to require a complete scenario-owned source set.

## Decision

Introduce a top-level `generation_sources` block in schema `1.2` scenario manifests. Each supported source kind accepts `"scenario"` or `"default"`, and `fallback_to_default` controls missing scenario-owned preset files.

When `fallback_to_default` is `false`, `scenario_loader.load()` performs a Phase A fail-fast check for every source kind mapped to a preset file. Missing required files raise `ScenarioValidationError` at load time and include the scenario id, source kind, and expected preset file path.

Runtime generators use `resolve_source(kind)` and receive a `SourceHandle` containing loaded data and provenance for debugging. In v1.2 the routed generators are names, personas, weapons, techniques, and sect selection.

## Alternatives Considered

Single all-or-nothing flag:
Too blunt. Some scenarios may want scenario-owned sects and names while intentionally using default weapons or techniques.

Embedding pools directly in `scenario.json`:
This would bloat scenario manifests, duplicate preset data, and make pool reuse across scenarios harder.

Requiring every preset to be complete:
Too heavy for new scenario authors. `fallback_to_default: true` preserves a minimum viable path, while bundled strict scenarios can opt into load-time enforcement.

## Consequences

Existing schema `0.1`, `0.2`, `1.0`, and `1.1` scenarios continue to load. If `generation_sources` is omitted, runtime resolution preserves v1.1 implicit-default behavior.

`liuchao` and `sanguo` now declare all ten generation sources as scenario-owned with `fallback_to_default: false`, so their required preset files must exist. v1.2 ships minimal scenario-owned stubs for races, roots, techniques, and weapons.

Sandbox mode remains default-sourced unless an explicit non-scenario preset is selected for legacy preset tests or tooling.

Mod import contract unchanged; v1.2 does not introduce mod-owned generation sources. The v1.0 mod platform (5 extension kinds: asset / llm_prompt / locale / predicate / effect) is preserved as-is, and `tests/test_mod_platform.py` continues to pass without modification. Future support for mod-owned source pools is deferred to a separate v1.3 spec that will need to define mod × scenario priority resolution and load-time validation across the mod stack.
