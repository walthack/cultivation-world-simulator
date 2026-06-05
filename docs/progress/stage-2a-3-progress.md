# Stage 2a-3 Progress: Realm Aliases and DSL Alignment

## Status

Done. Git commit was intentionally skipped in this sandbox; Hassan will batch commit/push after review.

## Files changed/added

- `config/presets/default/realms.json`
- `config/presets/liuchao/realms.json`
- `src/config/__init__.py`
- `src/config/presets.py`
- `src/scenario/schema_constants.py`
- `src/scenario/condition_evaluator.py`
- `src/scenario/effect_applier.py`
- `src/systems/cultivation_display.py`
- `tests/test_scenario_schema_v02_realm_dsl.py`
- `docs/adr/adr-0001-dsl-naming.md`

## Key design decision

`realms.json` now keeps the existing `realm_order` contract and adds a `realms` object list with `id`, `canonical_name`, and `display_name`. Existing startup behavior is preserved because `get_preset_realm_order()` still returns the same ordered ids.

DSL naming is frozen around Stage 1 implementation names. The older external v0.1 document names are documented as migration drift in `docs/adr/adr-0001-dsl-naming.md`, but Batch A does not accept both old and new names as aliases.

## Self-test

Command:

```bash
source .venv/bin/activate && CWS_DATA_DIR=/private/tmp/claude-501/cws-data pytest tests/test_scenario_*.py -v
```

Actual response:

```text
============================== 70 passed in 2.15s ==============================
```
