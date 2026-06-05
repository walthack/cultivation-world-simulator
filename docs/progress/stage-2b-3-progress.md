# Stage 2b-3 Progress: Region Vocab

## Status

Done. No git commit/push in sandbox.

## Files changed/added

- `config/presets/default/regions.json`
- `config/presets/liuchao/regions.json`
- `src/config/presets.py`
- `src/scenario/scenario_loader.py`
- `tests/test_scenario_schema_v02_regions.py`

## Key design decision

Region vocab is a preset-level list that unifies existing CWS `city_region.csv`, `cultivate_region.csv`, and `normal_region.csv` into one schema with `type: city | cultivate | normal`. Existing runtime map/region classes are not modified.

v0.2 region references are optional and validation is gated on `schema_version: "0.2"`:

- `scenario.initial_state.avatars[].location_region_id`
- `scenario.initial_state.sects[].headquarters_region_id`
- `timeline.events[].trigger.at_region_id`

Default regions are derived from CWS CSV and keep `dynasty_id: null` to avoid changing default sandbox behavior. Liuchao regions include a minimal dynasty-linked geography for Batch B validation.

## Self-test

Command:

```bash
source .venv/bin/activate && CWS_DATA_DIR=/private/tmp/claude-501/cws-data pytest -v
```

Actual response:

```text
3 failed, 1598 passed, 2 skipped, 1 warning in 53.82s
```

Batch B region tests all passed:

```text
tests/test_scenario_schema_v02_regions.py::test_default_regions_include_three_region_types PASSED
tests/test_scenario_schema_v02_regions.py::test_v02_avatar_location_region_ref_passes PASSED
tests/test_scenario_schema_v02_regions.py::test_v02_avatar_location_region_unknown_raises PASSED
tests/test_scenario_schema_v02_regions.py::test_v02_sect_headquarters_region_ref_passes PASSED
tests/test_scenario_schema_v02_regions.py::test_v02_sect_headquarters_region_unknown_raises PASSED
tests/test_scenario_schema_v02_regions.py::test_v02_timeline_trigger_region_ref_passes PASSED
tests/test_scenario_schema_v02_regions.py::test_v02_timeline_trigger_region_unknown_raises PASSED
tests/test_scenario_schema_v02_regions.py::test_region_rejects_unknown_dynasty PASSED
tests/test_scenario_schema_v02_regions.py::test_v01_scenario_without_region_fields_still_loads PASSED
```

Unrelated full-suite failures remain the same three `tests/test_game_init_integration.py` sect-selection mock assertions recorded in `stage-2b-1-progress.md`.
