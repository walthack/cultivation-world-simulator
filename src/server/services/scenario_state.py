from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config.data_paths import get_data_paths


def _state_path() -> Path:
    return get_data_paths().root / "scenarios_state.json"


def get_state() -> dict[str, dict[str, bool]]:
    path = _state_path()
    if not path.exists():
        return {}

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(raw, dict):
        return {}

    state: dict[str, dict[str, bool]] = {}
    for scenario_id, entry in raw.items():
        if isinstance(scenario_id, str) and isinstance(entry, dict):
            enabled = entry.get("enabled")
            if isinstance(enabled, bool):
                state[scenario_id] = {"enabled": enabled}
    return state


def is_enabled(scenario_id: str) -> bool:
    entry = get_state().get(scenario_id)
    if entry is None:
        return True
    return bool(entry.get("enabled", True))


def _write_state(state: dict[str, dict[str, bool]]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(path)


def set_enabled(scenario_id: str, enabled: bool) -> dict[str, Any]:
    state = get_state()
    state[str(scenario_id)] = {"enabled": bool(enabled)}
    _write_state(state)
    return {"scenario_id": str(scenario_id), "enabled": bool(enabled)}


def remove(scenario_id: str) -> None:
    state = get_state()
    if str(scenario_id) in state:
        del state[str(scenario_id)]
        _write_state(state)
