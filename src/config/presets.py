from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


DEFAULT_PRESET_ID = "default"
_ACTIVE_PRESET_ID = DEFAULT_PRESET_ID
TECHNIQUE_GRADES = {"mortal", "earth", "heaven", "divine"}


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


def get_preset_realms(preset_id: str | None = None) -> list[dict[str, Any]]:
    data = load_preset_json(preset_id, "realms.json")
    realms = data.get("realms")
    if realms is None:
        return [
            {"id": realm_id, "canonical_name": realm_id, "display_name": realm_id}
            for realm_id in get_preset_realm_order(preset_id)
        ]
    if not isinstance(realms, list):
        raise PresetConfigError("realms.json field realms must be a list")
    items: list[dict[str, Any]] = []
    for item in realms:
        if not isinstance(item, dict):
            raise PresetConfigError("realms.json field realms entries must be objects")
        realm_id = item.get("id")
        if not isinstance(realm_id, str) or not realm_id:
            raise PresetConfigError("realms.json field realms[].id must be a non-empty string")
        items.append(
            {
                "id": realm_id,
                "canonical_name": str(item.get("canonical_name") or realm_id),
                "display_name": str(item.get("display_name") or item.get("canonical_name") or realm_id),
            }
        )
    return items


def get_preset_realm_by_canonical_name(preset_id: str | None, canonical_name: str) -> str | None:
    normalized = str(canonical_name).strip().upper()
    for item in get_preset_realms(preset_id):
        if str(item["canonical_name"]).strip().upper() == normalized:
            return str(item["id"])
    return None


def get_preset_realm_display_name(preset_id: str | None, realm_id: str) -> str:
    target = str(realm_id)
    for item in get_preset_realms(preset_id):
        if str(item["id"]) == target:
            return str(item["display_name"])
    return target


def get_preset_stage_order(preset_id: str | None = None) -> list[str]:
    data = load_preset_json(preset_id, "realms.json")
    order = data.get("stage_order", [])
    if not isinstance(order, list):
        raise PresetConfigError("realms.json field stage_order must be a list")
    return [str(item) for item in order]


def _ids_from_collection(data: dict[str, Any], field_name: str, legacy_field_name: str | None = None) -> set[str]:
    values = data.get(field_name, [])
    ids: set[str] = set()
    if isinstance(values, dict):
        ids.update(str(key) for key in values)
    elif isinstance(values, list):
        for item in values:
            if isinstance(item, dict):
                item_id = item.get("id")
            else:
                item_id = item
            if item_id is not None:
                ids.add(str(item_id))
    else:
        raise PresetConfigError(f"{field_name} must be a list or object")

    if legacy_field_name:
        legacy_values = data.get(legacy_field_name, [])
        if not isinstance(legacy_values, list):
            raise PresetConfigError(f"{legacy_field_name} must be a list")
        ids.update(str(item) for item in legacy_values)
    return ids


def _collection_items(data: dict[str, Any], field_name: str) -> list[dict[str, Any]]:
    values = data.get(field_name, [])
    if isinstance(values, dict):
        values = [{"id": key, **value} if isinstance(value, dict) else {"id": key} for key, value in values.items()]
    if not isinstance(values, list):
        raise PresetConfigError(f"{field_name} must be a list or object")
    items: list[dict[str, Any]] = []
    for item in values:
        if isinstance(item, str):
            items.append({"id": item})
        elif isinstance(item, dict):
            items.append(dict(item))
        else:
            raise PresetConfigError(f"{field_name} entries must be objects or strings")
    return items


def get_preset_realm_enum_order(preset_id: str | None = None):
    from src.systems.cultivation import Realm

    return [Realm.from_str(item) for item in get_preset_realm_order(preset_id)]


def get_preset_name_templates(preset_id: str | None = None) -> dict[str, Any]:
    return load_preset_json(preset_id, "name_templates.json")


def get_preset_persona_keys(preset_id: str | None = None) -> set[str]:
    data = load_preset_json(preset_id, "personas.json")
    return {item.upper() for item in _ids_from_collection(data, "personas", "persona_keys")}


def get_preset_goldfinger_keys(preset_id: str | None = None) -> set[str]:
    data = load_preset_json(preset_id, "goldfingers.json")
    return {item.upper() for item in _ids_from_collection(data, "goldfingers", "goldfinger_keys")}


def get_preset_race_ids(preset_id: str | None = None) -> set[str]:
    data = load_preset_json(preset_id, "races.json")
    return _ids_from_collection(data, "races")


def get_preset_root_ids(preset_id: str | None = None) -> set[str]:
    data = load_preset_json(preset_id, "roots.json")
    return {item.upper() for item in _ids_from_collection(data, "roots")}


def get_preset_personas(preset_id: str | None = None) -> list[dict[str, Any]]:
    return _collection_items(load_preset_json(preset_id, "personas.json"), "personas")


def get_preset_goldfingers(preset_id: str | None = None) -> list[dict[str, Any]]:
    return _collection_items(load_preset_json(preset_id, "goldfingers.json"), "goldfingers")


def get_preset_techniques(preset_id: str | None = None) -> list[dict[str, Any]]:
    items = _collection_items(load_preset_json(preset_id, "techniques.json"), "techniques")
    for item in items:
        grade = item.get("grade")
        if grade not in TECHNIQUE_GRADES:
            raise PresetConfigError(f"techniques.json invalid grade for {item.get('id')}: {grade}")
    return items


def get_preset_technique_ids(preset_id: str | None = None) -> set[str]:
    return {str(item.get("id")) for item in get_preset_techniques(preset_id)}


def get_preset_weapons(preset_id: str | None = None) -> list[dict[str, Any]]:
    items = _collection_items(load_preset_json(preset_id, "weapons.json"), "weapons")
    for item in items:
        tier = item.get("tier")
        if not isinstance(tier, int) or not 1 <= tier <= 9:
            raise PresetConfigError(f"weapons.json invalid tier for {item.get('id')}: {tier}")
    return items


def get_preset_weapon_ids(preset_id: str | None = None) -> set[str]:
    return {str(item.get("id")) for item in get_preset_weapons(preset_id)}
