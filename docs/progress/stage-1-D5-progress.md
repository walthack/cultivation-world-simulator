# Stage 1 D5 Progress

Status: ✅ complete with local pytest blocker noted.

## Files Changed/Added

- `src/scenario/__init__.py`
- `src/scenario/scenario_loader.py`
- `config/scenarios/sample/scenario.json`
- `config/scenarios/sample/timeline.json`
- `config/presets/default/personas.json`
- `config/presets/default/goldfingers.json`
- `config/presets/liuchao/personas.json`
- `config/presets/liuchao/goldfingers.json`
- `tests/test_scenario_stage1.py`

## Key Design Decision

`scenario_loader.load(scenario_id)` now reads `config/scenarios/<scenario_id>/scenario.json` and optional `timeline.json`, validates Schema v0.1 required fields, validates preset existence, and checks refs for sect ids, realms, persona keys, goldfinger keys, initial relationships, sect membership, and timeline event dependencies.

Validation uses explicit Python checks instead of adding a new external `jsonschema` dependency. Errors use `ScenarioValidationError` / `MissingReferenceError` with field path, expected value, and actual value.

## Self-Test

Command requested by verification loop:

```bash
source .venv/bin/activate && pytest tests/test_scenario_stage1.py -k scenario_loader_loads_sample_scenario -q
```

Actual response:

```text
zsh:1: command not found: pytest
```

Direct validation fallback:

```bash
CWS_DATA_DIR=/private/tmp/cws-stage1-data .venv/bin/python3.14 - <<'PY'
from src.scenario.scenario_loader import load
scenario = load('sample')
print({'scenario_id': scenario.scenario_id, 'preset_id': scenario.preset_id, 'events': [event['id'] for event in scenario.timeline]})
PY
```

Actual response:

```text
{'scenario_id': 'sample', 'preset_id': 'default', 'events': ['sample-main-event']}
```
