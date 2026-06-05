# ADR-020: Mod Platform Architecture

## Status

Accepted for v1.0.

## Context

The scenario engine is extended into a local generic mod platform. Mods are installed under `$CWS_DATA_DIR/mods/<mod_id>/` and are tracked by data-root registry files, not by modifying bundled game files.

## Decision

The backend owns a `src/mod_platform/` package with registry, import, loading, conflict detection, and extension point modules. Load order is stored in `$CWS_DATA_DIR/mods_load_order.json`; installed metadata is stored in `$CWS_DATA_DIR/mods_registry.json`.

Extension points are categorized as data-only or Python:

- Data-only: asset overlays, LLM prompt templates, localization strings.
- Python: scenario predicates, scenario effects, lifecycle hooks.

Data-only extensions are always active for enabled mods. Python extensions are registered only when `session.allow_trusted_python_mods` is enabled.

## Consequences

No marketplace or online community service is introduced in v1.0. The platform is strictly local and additive to the existing scenario engine DSL.
