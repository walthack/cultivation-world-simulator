# Stage 1 D2 Progress

Status: ✅ complete with local pytest blocker noted.

## Files Changed/Added

- `config/presets/default/sects.json`
- `config/presets/liuchao/sects.json`
- `src/config/presets.py`
- `src/config/__init__.py`
- `src/server/init_flow.py`
- `tests/test_scenario_stage1.py`

## Key Design Decision

The default sect pool is externalized as `config/presets/default/sects.json` with ids `1..14`, matching the existing static `sect.csv` pool. Startup still reloads static sect definitions from CSV, then `_select_existed_sects()` filters by the active preset pool. Because the default preset includes all current sect ids, default startup behavior is unchanged.

## Self-Test

Command requested by verification loop:

```bash
source .venv/bin/activate && pytest tests/test_scenario_stage1.py -k default_preset_sect_pool -q
```

Actual response:

```text
zsh:1: command not found: pytest
```

Direct validation fallback:

```bash
.venv/bin/python3.14 - <<'PY'
from src.config.presets import get_preset_sect_ids, set_active_preset
from src.server.init_flow import _select_existed_sects
class Sect:
    def __init__(self, id): self.id = id
set_active_preset('default')
ids = get_preset_sect_ids('default')
selected = _select_existed_sects(sects_by_id={i: Sect(i) for i in ids}, needed_sects=14)
print({'ids': ids, 'selected': sorted(s.id for s in selected)})
PY
```

Actual response:

```text
{'ids': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14], 'selected': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]}
```
