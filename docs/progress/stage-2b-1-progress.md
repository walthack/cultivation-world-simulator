# Stage 2b-1 Progress: Dynasty

## Status

Done. No git commit/push in sandbox.

## Files changed/added

- `config/presets/default/dynasties.json`
- `config/presets/liuchao/dynasties.json`
- `src/config/__init__.py`
- `src/config/presets.py`
- `src/scenario/scenario_loader.py`
- `tests/test_scenario_schema_v02_dynasties.py`

## Key design decision

Dynasty is modeled as preset vocab plus optional `scenario.initial_state.dynasties` state. The v0.2 validator accepts dynasty entries only when present, and new validation stays gated on `schema_version: "0.2"`.

Because Batch B order creates `orthodoxies.json` and `regions.json` later, dynasty validation only loads those pools when a dynasty actually contains `orthodoxy_ids`, `capital_region_id`, or `territory_region_ids`. This keeps v0.1/v0.2 scenarios with no dynasty refs backward-compatible while still rejecting bad refs when the fields are used.

Liuchao preset includes 4 confirmed dynasties (`song`, `han`, `jin`, `xishu`), plus `qin` and one explicit TODO placeholder encoded via `description` / `tags` because JSON cannot carry comments.

## Self-test

Command:

```bash
source .venv/bin/activate && CWS_DATA_DIR=/private/tmp/claude-501/cws-data pytest -v
```

Actual response:

```text
3 failed, 1585 passed, 2 skipped, 1 warning in 54.51s
```

Batch B dynasty tests all passed:

```text
tests/test_scenario_schema_v02_dynasties.py::test_v02_dynasty_valid_refs_pass PASSED
tests/test_scenario_schema_v02_dynasties.py::test_v02_dynasty_unknown_capital_region_raises PASSED
tests/test_scenario_schema_v02_dynasties.py::test_v02_dynasty_unknown_territory_region_raises PASSED
tests/test_scenario_schema_v02_dynasties.py::test_v02_dynasty_unknown_orthodoxy_raises PASSED
tests/test_scenario_schema_v02_dynasties.py::test_v02_dynasty_unknown_ruler_raises PASSED
tests/test_scenario_schema_v02_dynasties.py::test_v02_dynasty_relation_value_range_validation PASSED
tests/test_scenario_schema_v02_dynasties.py::test_v01_without_dynasties_loads PASSED
```

The 3 full-suite failures were unrelated existing init mock/preset sect-selection assertions in:

- `tests/test_game_init_integration.py::TestInitGameAsyncWithSects::test_init_selects_random_sects`
- `tests/test_game_init_integration.py::TestInitGameAsyncWithSects::test_init_sets_world_existed_sects`
- `tests/test_game_init_integration.py::TestInitGameAsyncEdgeCases::test_init_more_sects_requested_than_available`
