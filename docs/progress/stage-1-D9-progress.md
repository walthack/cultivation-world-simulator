# Stage 1 D9 Progress

Status: ⚠️ data complete; server `--scenario` CLI wiring blocked by action_safety.

## Files Changed/Added

- `config/scenarios/liuchao/scenario.json`
- `config/scenarios/liuchao/timeline.json`
- `config/presets/liuchao/sects.json`
- `config/presets/liuchao/realms.json`
- `config/presets/liuchao/personas.json`
- `config/presets/liuchao/goldfingers.json`

## Key Design Decision

The minimal liuchao scenario contains exactly 3 starter avatars: 程宗扬, 王哲, 小紫. The timeline contains 2 events, including the required Y2.M3 `wang-zhe-passes-jiuyang` main event. The liuchao preset has a minimal sect mapping and a nine-realm order.

Full 70+ entry liuchao data was intentionally not imported.

## Self-Test

Loader validation command:

```bash
source .venv/bin/activate && CWS_DATA_DIR=/private/tmp/cws-stage1-data python3.14 - <<'PY'
from src.scenario.scenario_loader import load
scenario = load('liuchao')
print({'scenario_id': scenario.scenario_id, 'preset_id': scenario.preset_id, 'avatar_count': len(scenario.scenario['initial_state']['avatars']), 'events': [event['id'] for event in scenario.timeline]})
PY
```

Actual response:

```text
{'scenario_id': 'liuchao', 'preset_id': 'liuchao', 'avatar_count': 3, 'events': ['liuchao-opening', 'wang-zhe-passes-jiuyang']}
```

Requested uvicorn validation command:

```bash
source .venv/bin/activate && CWS_DATA_DIR=/private/tmp/cws-stage1-data python3.14 -m uvicorn src.server.host_app:app --host 127.0.0.1 --port 8003 --scenario liuchao
```

Actual response:

```text
Usage: python -m uvicorn [OPTIONS] APP
Try 'python -m uvicorn --help' for help.

Error: No such option '--scenario'. (Did you mean one of: '--ssl-version', '--version'?)
```

## Blocker

Supporting `--scenario liuchao` for uvicorn startup requires changing server CLI parsing in `src/server/main.py` or related server files. The task's action_safety only allows changes under `src/scenario/`, `config/scenarios/liuchao/`, `config/presets/liuchao/`, and `tests/test_scenario_*.py`, so this wiring was not modified.
