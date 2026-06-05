# Stage 2b Final Report

## Status

| Sub-stage | Status | Notes |
|---|---|---|
| 2b-1 Dynasty | ✅ Done | Added preset dynasty vocab, optional scenario dynasties, v0.2 ref validation, liuchao 4 confirmed dynasties + 2 placeholders. |
| 2b-2 Orthodoxy | ✅ Done | Added multi-axis ideology vocab and numeric axes validation. |
| 2b-3 Region vocab | ✅ Done | Added unified region vocab and v0.2 avatar/sect/timeline region references. |
| 2b-4 Region map skeleton | ✅ Done | Added abstract adjacency graph and ADR for tile-grid downgrade. |

## Pytest Output

Full suite command:

```bash
source .venv/bin/activate && CWS_DATA_DIR=/private/tmp/claude-501/cws-data pytest -v
```

Final full-suite response:

```text
3 failed, 1603 passed, 2 skipped, 1 warning in 60.24s
```

The 3 failures are unchanged unrelated init integration mock assertions:

- `tests/test_game_init_integration.py::TestInitGameAsyncWithSects::test_init_selects_random_sects`
- `tests/test_game_init_integration.py::TestInitGameAsyncWithSects::test_init_sets_world_existed_sects`
- `tests/test_game_init_integration.py::TestInitGameAsyncEdgeCases::test_init_more_sects_requested_than_available`

Targeted Stage 2 schema command:

```bash
source .venv/bin/activate && CWS_DATA_DIR=/private/tmp/claude-501/cws-data pytest tests/test_scenario_schema_v02_*.py -v
```

Targeted response:

```text
50 passed in 1.67s
```

## Commit-ready File List

- `config/presets/default/dynasties.json`
- `config/presets/default/orthodoxies.json`
- `config/presets/default/regions.json`
- `config/presets/default/region_adjacency.json`
- `config/presets/liuchao/dynasties.json`
- `config/presets/liuchao/orthodoxies.json`
- `config/presets/liuchao/regions.json`
- `config/presets/liuchao/region_adjacency.json`
- `docs/adr/ADR-004-region-map-abstract-graph.md`
- `docs/progress/schema-v0.2-batch-b-spec-update.md`
- `docs/progress/stage-2b-1-progress.md`
- `docs/progress/stage-2b-2-progress.md`
- `docs/progress/stage-2b-3-progress.md`
- `docs/progress/stage-2b-4-progress.md`
- `docs/progress/stage-2b-final-report.md`
- `src/config/__init__.py`
- `src/config/presets.py`
- `src/scenario/scenario_loader.py`
- `tests/test_scenario_schema_v02_dynasties.py`
- `tests/test_scenario_schema_v02_orthodoxies.py`
- `tests/test_scenario_schema_v02_regions.py`
- `tests/test_scenario_schema_v02_region_adjacency.py`

## ADRs

- `docs/adr/ADR-004-region-map-abstract-graph.md`

## Dashboard Update Suggestions

- Mark Stage 2b v0.2 Schema Batch B as done:
  - 2b-1 Dynasty / Orthodoxy foundation: ✅
  - 2b-2 Region vocab: ✅
  - 2b-3 Region map skeleton: ✅
- Update v0.2 schema coverage to include Dynasty, Orthodoxy, Region vocab, and abstract Region adjacency.
- Note residual test risk: full pytest currently has 3 unrelated `test_game_init_integration.py` failures around mocked sect selection; all Stage 2 scenario schema tests pass.
- Next recommended stage: Stage 2c controlled-avatar perspective + richer liuchao content import.
