from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


DEFAULT_PRESET_ID = "default"
_ACTIVE_PRESET_ID = DEFAULT_PRESET_ID


class PresetConfigError(ValueError):
    pass


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_presets_root() -> Path:
    return get_project_root() / "config" / "presets"


def set_active_preset(preset_id: str | None) -> str:
    global _ACTIVE_PRESET_ID
    normalized = str(preset_id or DEFAULT_PRESET_ID).strip() or DEFAULT_PRESET_ID
    if not (get_presets_root() / normalized).is_dir():
        raise PresetConfigError(f"Unknown preset: {normalized}")
    _ACTIVE_PRESET_ID = normalized
    os.environ["CWS_PRESET"] = normalized
    return _ACTIVE_PRESET_ID


def get_active_preset_id() -> str:
    env_preset = str(os.environ.get("CWS_PRESET", "") or "").strip()
    if env_preset:
        return env_preset
    return _ACTIVE_PRESET_ID


def load_preset_json(preset_id: str | None, filename: str) -> dict[str, Any]:
    normalized = str(preset_id or get_active_preset_id() or DEFAULT_PRESET_ID)
    path = get_presets_root() / normalized / filename
    if not path.exists():
        raise PresetConfigError(f"Missing preset file: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PresetConfigError(f"Invalid preset JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise PresetConfigError(f"Preset file must contain an object: {path}")
    return data


def get_preset_sect_ids(preset_id: str | None = None) -> list[int]:
    data = load_preset_json(preset_id, "sects.json")
    ids = data.get("sect_ids", [])
    if not isinstance(ids, list):
        raise PresetConfigError("sects.json field sect_ids must be a list")
    return [int(item) for item in ids]


def get_preset_realm_order(preset_id: str | None = None) -> list[str]:
    data = load_preset_json(preset_id, "realms.json")
    order = data.get("realm_order", [])
    if not isinstance(order, list):
        raise PresetConfigError("realms.json field realm_order must be a list")
    return [str(item) for item in order]


def get_preset_stage_order(preset_id: str | None = None) -> list[str]:
    data = load_preset_json(preset_id, "realms.json")
    order = data.get("stage_order", [])
    if not isinstance(order, list):
        raise PresetConfigError("realms.json field stage_order must be a list")
    return [str(item) for item in order]


def get_preset_realm_enum_order(preset_id: str | None = None):
    from src.systems.cultivation import Realm

    return [Realm.from_str(item) for item in get_preset_realm_order(preset_id)]


def get_preset_name_templates(preset_id: str | None = None) -> dict[str, Any]:
    return load_preset_json(preset_id, "name_templates.json")


def get_preset_persona_keys(preset_id: str | None = None) -> set[str]:
    data = load_preset_json(preset_id, "personas.json")
    keys = data.get("persona_keys", [])
    if not isinstance(keys, list):
        raise PresetConfigError("personas.json field persona_keys must be a list")
    return {str(item).upper() for item in keys}


def get_preset_goldfinger_keys(preset_id: str | None = None) -> set[str]:
    data = load_preset_json(preset_id, "goldfingers.json")
    keys = data.get("goldfinger_keys", [])
    if not isinstance(keys, list):
        raise PresetConfigError("goldfingers.json field goldfinger_keys must be a list")
    return {str(item).upper() for item in keys}
