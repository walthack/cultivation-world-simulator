# Stage 2b-2 Progress: Orthodoxy

## Status

Done. No git commit/push in sandbox.

## Files changed/added

- `config/presets/default/orthodoxies.json`
- `config/presets/liuchao/orthodoxies.json`
- `src/config/presets.py`
- `tests/test_scenario_schema_v02_orthodoxies.py`

## Key design decision

Orthodoxy is a preset-level multi-axis ideology vocab. The existing CWS `orthodoxy.csv` has simple rows with effect DSL; v0.2 keeps orthodoxy as data-only schema and maps each id to numeric `axes` positions plus freeform `tags`.

Default preset axes are conservative projections of existing CWS orthodoxy concepts. Liuchao uses a richer axis set (`汉统`, `胡`, `玄学`, `名教`, `武`) to support later dynasty/sect relationship reasoning without adding a hard political simulation system.

## Self-test

Command:

```bash
source .venv/bin/activate && CWS_DATA_DIR=/private/tmp/claude-501/cws-data pytest -v
```

Actual response:

```text
3 failed, 1589 passed, 2 skipped, 1 warning in 53.13s
```

Batch B orthodoxy tests all passed:

```text
tests/test_scenario_schema_v02_orthodoxies.py::test_default_orthodoxy_axes_are_numeric PASSED
tests/test_scenario_schema_v02_orthodoxies.py::test_liuchao_orthodoxy_contains_multi_axis_positions PASSED
tests/test_scenario_schema_v02_orthodoxies.py::test_orthodoxy_rejects_non_numeric_axis PASSED
tests/test_scenario_schema_v02_orthodoxies.py::test_v01_scenario_still_loads_after_orthodoxy_schema PASSED
```

Unrelated full-suite failures remain the same three `tests/test_game_init_integration.py` sect-selection mock assertions recorded in `stage-2b-1-progress.md`.
