from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config.data_paths import get_data_paths

from .mod_extension_points import ModMetadata, mod_declares_python


def mods_root() -> Path:
    root = get_data_paths().root / "mods"
    root.mkdir(parents=True, exist_ok=True)
    return root


def registry_path() -> Path:
    return get_data_paths().root / "mods_registry.json"


def load_order_path() -> Path:
    return get_data_paths().root / "mods_load_order.json"


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_mod_json(mod_dir: Path) -> ModMetadata:
    path = mod_dir / "mod.json"
    if not path.exists():
        raise ValueError(f"Missing mod.json: {mod_dir}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("mod.json must be an object")
    mod_id = str(payload.get("mod_id", "")).strip()
    if not mod_id or "/" in mod_id or "\\" in mod_id or mod_id.startswith("."):
        raise ValueError("mod_id must be a safe non-empty id")
    metadata = ModMetadata(
        mod_id=mod_id,
        name=str(payload.get("name") or mod_id),
        version=str(payload.get("version") or "0.0.0"),
        author=str(payload.get("author") or ""),
        description=str(payload.get("description") or ""),
        fingerprint=str(payload.get("fingerprint") or ""),
        dependencies=list(payload.get("dependencies") or []),
        extensions=dict(payload.get("extensions") or {}),
        path=str(mod_dir),
        enabled=True,
    )
    metadata.python_hooks_declared = mod_declares_python(metadata)
    return metadata


def list_installed_mods() -> list[ModMetadata]:
    state = _read_json(registry_path(), {})
    if not isinstance(state, dict):
        state = {}
    mods: list[ModMetadata] = []
    for mod_id, payload in state.items():
        if not isinstance(payload, dict):
            continue
        metadata = ModMetadata(
            mod_id=str(payload.get("mod_id") or mod_id),
            name=str(payload.get("name") or mod_id),
            version=str(payload.get("version") or "0.0.0"),
            author=str(payload.get("author") or ""),
            description=str(payload.get("description") or ""),
            fingerprint=str(payload.get("fingerprint") or ""),
            dependencies=list(payload.get("dependencies") or []),
            extensions=dict(payload.get("extensions") or {}),
            path=str(payload.get("path") or mods_root() / mod_id),
            enabled=bool(payload.get("enabled", True)),
            python_hooks_enabled=bool(payload.get("python_hooks_enabled", False)),
            python_hooks_declared=bool(payload.get("python_hooks_declared", False)),
        )
        mods.append(metadata)
    return mods


def save_installed_mods(mods: list[ModMetadata]) -> None:
    _write_json(registry_path(), {mod.mod_id: mod.to_dict() for mod in mods})
    existing_order = get_load_order()
    next_order = [mod_id for mod_id in existing_order if any(mod.mod_id == mod_id for mod in mods)]
    for mod in mods:
        if mod.mod_id not in next_order:
            next_order.append(mod.mod_id)
    set_load_order(next_order)


def upsert_mod(metadata: ModMetadata) -> ModMetadata:
    mods = [mod for mod in list_installed_mods() if mod.mod_id != metadata.mod_id]
    mods.append(metadata)
    save_installed_mods(mods)
    return metadata


def remove_mod(mod_id: str) -> None:
    save_installed_mods([mod for mod in list_installed_mods() if mod.mod_id != mod_id])


def get_mod(mod_id: str) -> ModMetadata | None:
    for mod in list_installed_mods():
        if mod.mod_id == mod_id:
            return mod
    return None


def set_enabled(mod_id: str, enabled: bool) -> ModMetadata:
    mods = list_installed_mods()
    for mod in mods:
        if mod.mod_id == mod_id:
            mod.enabled = bool(enabled)
            save_installed_mods(mods)
            return mod
    raise KeyError(mod_id)


def get_load_order() -> list[str]:
    payload = _read_json(load_order_path(), [])
    if not isinstance(payload, list):
        payload = []
    known = {mod.mod_id for mod in list_installed_mods()}
    order = [str(item) for item in payload if str(item) in known]
    for mod_id in sorted(known):
        if mod_id not in order:
            order.append(mod_id)
    return order


def set_load_order(mod_ids: list[str]) -> list[str]:
    known = {mod.mod_id for mod in list_installed_mods()}
    order = [str(item) for item in mod_ids if str(item) in known]
    for mod_id in sorted(known):
        if mod_id not in order:
            order.append(mod_id)
    _write_json(load_order_path(), order)
    return order


def ordered_mods(*, enabled_only: bool = False) -> list[ModMetadata]:
    by_id = {mod.mod_id: mod for mod in list_installed_mods()}
    ordered = [by_id[mod_id] for mod_id in get_load_order() if mod_id in by_id]
    if enabled_only:
        ordered = [mod for mod in ordered if mod.enabled]
    return ordered
