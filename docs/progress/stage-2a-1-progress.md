# Stage 2a-1 Progress: Character Foundation

## Status

Done. Git commit was intentionally skipped in this sandbox; Hassan will batch commit/push after review.

## Files changed/added

- `config/presets/default/races.json`
- `config/presets/default/roots.json`
- `config/presets/default/personas.json`
- `config/presets/default/goldfingers.json`
- `src/config/presets.py`
- `src/scenario/scenario_loader.py`
- `tests/test_scenario_schema_v02_character_foundation.py`

## Key design decision

Schema v0.2 is implemented as a backward-compatible superset of v0.1. The loader accepts both `schema_version: "0.1"` and `"0.2"`, but new reference validation for `race_id` and `root_id` only runs when the scenario declares `"0.2"`.

`personas.json` and `goldfingers.json` now carry full object models while preserving legacy `persona_keys` / `goldfinger_keys` so Stage 1 callers and v0.1 scenarios keep working. Scenario avatar fields can still use legacy bare id strings; v0.2 also accepts full persona/goldfinger objects and preserves side-effect DSL data unchanged.

## Self-test

Command:

```bash
source .venv/bin/activate && CWS_DATA_DIR=/private/tmp/claude-501/cws-data pytest tests/test_scenario_*.py -v
```

Actual response:

```text
============================== 58 passed in 1.78s ==============================
```

Note: running without `CWS_DATA_DIR` failed before test collection because the sandbox cannot write logs under the default user data directory.
