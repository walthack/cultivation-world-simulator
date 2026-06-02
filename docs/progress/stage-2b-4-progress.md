# Stage 2b-4 Progress: Region Map Skeleton

## Status

Done. No git commit/push in sandbox.

## Files changed/added

- `config/presets/default/region_adjacency.json`
- `config/presets/liuchao/region_adjacency.json`
- `docs/adr/ADR-004-region-map-abstract-graph.md`
- `src/config/__init__.py`
- `src/config/presets.py`
- `tests/test_scenario_schema_v02_region_adjacency.py`

## Key design decision

CWS `region_map.csv` is a tile-level grid, so Batch B intentionally downgraded it to an abstract adjacency graph. The strategy is documented in `docs/adr/ADR-004-region-map-abstract-graph.md`.

Default `region_adjacency.json` was derived from orthogonal neighbor pairs in `static/game_configs/region_map.csv`, filtered to known `regions.json` ids. Liuchao uses a hand-authored minimal connected graph. The schema stores one undirected edge per pair with `relation` and `difficulty`; no coordinates, tile editor, pathfinding, or route solver were added.

## Self-test

Command:

```bash
source .venv/bin/activate && CWS_DATA_DIR=/private/tmp/claude-501/cws-data pytest -v
```

Actual response:

```text
3 failed, 1603 passed, 2 skipped, 1 warning in 60.24s
```

Batch B region adjacency tests all passed:

```text
tests/test_scenario_schema_v02_region_adjacency.py::test_default_region_adjacency_edges_reference_known_regions PASSED
tests/test_scenario_schema_v02_region_adjacency.py::test_liuchao_region_adjacency_is_connected PASSED
tests/test_scenario_schema_v02_region_adjacency.py::test_default_region_adjacency_connectivity_sanity PASSED
tests/test_scenario_schema_v02_region_adjacency.py::test_region_adjacency_rejects_unknown_region PASSED
tests/test_scenario_schema_v02_region_adjacency.py::test_region_adjacency_rejects_invalid_relation PASSED
```

Additional targeted schema verification:

```bash
source .venv/bin/activate && CWS_DATA_DIR=/private/tmp/claude-501/cws-data pytest tests/test_scenario_schema_v02_*.py -v
```

Actual response:

```text
50 passed in 1.67s
```

Unrelated full-suite failures remain the same three `tests/test_game_init_integration.py` sect-selection mock assertions recorded in `stage-2b-1-progress.md`.
