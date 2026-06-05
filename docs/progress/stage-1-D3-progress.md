# Stage 1 D3 Progress

Status: ✅ complete with local pytest blocker noted.

## Files Changed/Added

- `config/presets/default/realms.json`
- `config/presets/liuchao/realms.json`
- `src/config/presets.py`
- `src/config/__init__.py`
- `src/server/main.py`
- `tests/test_scenario_stage1.py`

## Key Design Decision

Realm order is externalized through `realms.json`. `--preset default` remains the default and maps to the existing realm sequence: `QI_REFINEMENT`, `FOUNDATION_ESTABLISHMENT`, `CORE_FORMATION`, `NASCENT_SOUL`. The `liuchao` preset is a placeholder with the same realm order until Stage 2 introduces a fuller world model.

`src/server/main.py` now accepts `--preset <id>` and `--preset=<id>` and sets the active preset before public query builders are created.

## Self-Test

Command requested by verification loop:

```bash
source .venv/bin/activate && pytest tests/test_scenario_stage1.py -k default_preset_realm_order -q
```

Actual response:

```text
zsh:1: command not found: pytest
```

Direct validation fallback:

```bash
.venv/bin/python3.14 - <<'PY'
from src.config.presets import get_preset_realm_order, get_preset_realm_enum_order, set_active_preset
set_active_preset('default')
print({'default': get_preset_realm_order('default'), 'enum_values': [realm.value for realm in get_preset_realm_enum_order('default')]})
set_active_preset('liuchao')
print({'liuchao': get_preset_realm_order('liuchao')})
set_active_preset('default')
PY
```

Actual response:

```text
{'default': ['QI_REFINEMENT', 'FOUNDATION_ESTABLISHMENT', 'CORE_FORMATION', 'NASCENT_SOUL'], 'enum_values': ['QI_REFINEMENT', 'FOUNDATION_ESTABLISHMENT', 'CORE_FORMATION', 'NASCENT_SOUL']}
{'liuchao': ['QI_REFINEMENT', 'FOUNDATION_ESTABLISHMENT', 'CORE_FORMATION', 'NASCENT_SOUL']}
```

CLI flag validation:

```bash
CWS_DATA_DIR=/private/tmp/cws-stage1-data .venv/bin/python3.14 - <<'PY'
import sys
sys.argv = ['uvicorn', '--preset', 'liuchao']
import src.server.main as main
print({'active_preset': main.ACTIVE_PRESET_ID})
PY
```

Actual response:

```text
[Config] Switched language context to zh-CN
Runtime mode: Development
Assets path: /Users/clawbot/Projects/cws-fork/assets
Web dist path: /Users/clawbot/Projects/cws-fork/web/dist
Warning: Web dist path not found: /Users/clawbot/Projects/cws-fork/web/dist.
{'active_preset': 'liuchao'}
```
