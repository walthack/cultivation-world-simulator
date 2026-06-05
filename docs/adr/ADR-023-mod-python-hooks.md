# ADR-023: Mod Python Hooks

## Status

Accepted for v1.0.

## Q1 Constraint

`session.allow_trusted_python_mods: bool = False (default)`

Default OFF:
- Mods install fine (all kinds)
- Data-only extensions active: asset overlays, LLM prompt templates (plain text f-string), localization strings
- Python hooks (predicates / effects / lifecycle hooks) are INERT — declared but NOT registered to runtime
- Mod Manager UI shows "Python hooks: disabled" badge per mod that ships Python

Toggle ON flow:
- Show trust warning modal BEFORE enabling: "You are about to enable Python mod execution. Untrusted mods can do anything the game can do. Continue?"
- After confirm: Python predicates / effects / lifecycle hooks become ACTIVE
- Mod Manager UI shows "Python hooks: enabled" warning badge

Implementation flag: session.allow_trusted_python_mods sibling to v0.8's advanced_runtime_control. mod_loader checks this flag before registering Python extensions.

## Decision

v1.0 uses a trust model with a safety gate. There is no Python sandbox. When the gate is off, the loader records Python declarations for UI display but does not import files from `rules/` or `code/`.

When enabled, predicates register through `condition_evaluator.register_predicate`, effects register through `effect_applier.register_effect`, and lifecycle hooks register through `python_hooks`.

## Consequences

The default behavior is installable but inert Python code. Users must explicitly accept the trust warning before Python mod execution is enabled.
