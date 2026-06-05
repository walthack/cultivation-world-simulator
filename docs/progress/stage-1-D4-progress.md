# Stage 1 D4 Progress

Status: ✅ complete with local pytest blocker noted.

## Files Changed/Added

- `config/presets/default/name_templates.json`
- `config/presets/liuchao/name_templates.json`
- `src/config/presets.py`
- `src/utils/name_generator.py`
- `tests/test_scenario_stage1.py`

## Key Design Decision

Default preset name generation remains CSV-driven (`mode: "csv"`), preserving existing behavior. The `liuchao` placeholder preset uses inline surname/given-name pools. `NameManager.reload()` applies active preset templates after normal CSV loading, so switching preset changes generated NPC names without replacing the existing name generation API.

## Self-Test

Command requested by verification loop:

```bash
source .venv/bin/activate && pytest tests/test_scenario_stage1.py -k liuchao_preset_changes_generated_name_style -q
```

Actual response:

```text
zsh:1: command not found: pytest
```

Direct validation fallback:

```bash
CWS_DATA_DIR=/private/tmp/cws-stage1-data .venv/bin/python3.14 - <<'PY'
from src.config.presets import set_active_preset
from src.utils import name_generator
from src.classes.gender import Gender
set_active_preset('liuchao')
name_generator.reload()
names = [name_generator.get_random_name(Gender.MALE) for _ in range(5)]
print({'liuchao_names': names})
set_active_preset('default')
name_generator.reload()
PY
```

Actual response:

```text
[Config] Switched language context to zh-CN
{'liuchao_names': ['程玄', '王宗扬', '紫玄', '程昭', '紫玄']}
```
