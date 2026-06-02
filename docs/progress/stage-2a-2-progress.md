# Stage 2a-2 Progress: Content Pools

## Status

Done. Git commit was intentionally skipped in this sandbox; Hassan will batch commit/push after review.

## Files changed/added

- `config/presets/default/techniques.json`
- `config/presets/default/weapons.json`
- `src/config/__init__.py`
- `src/config/presets.py`
- `src/scenario/scenario_loader.py`
- `tests/test_scenario_schema_v02_content_pools.py`

## Key design decision

Technique and weapon pools are preset-level vocabularies. Scenario v0.2 avatars may optionally reference them with:

- `avatars[].techniques`: list of `{technique_id, level}`
- `avatars[].weapons`: list of `{weapon_id, quantity}`

Reference validation is gated on `schema_version: "0.2"` and v0.1 scenarios without the new fields still load unchanged.

The default preset data was mechanically derived from `static/game_configs/technique.csv` and `static/game_configs/weapon.csv`. Existing CWS technique grades were mapped into the v0.2 schema enum as `LOWER -> mortal`, `MIDDLE -> earth`, `UPPER -> heaven`; `divine` is reserved for future scenario content. Weapon realm grades were converted to tier values in the 1-9 range.

## Self-test

Command:

```bash
source .venv/bin/activate && CWS_DATA_DIR=/private/tmp/claude-501/cws-data pytest tests/test_scenario_*.py -v
```

Actual response:

```text
============================== 66 passed in 2.14s ==============================
```
