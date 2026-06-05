from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

from .mod_extension_points import LIFECYCLE_HOOKS, ModMetadata


_LIFECYCLE_HOOKS: dict[str, list[tuple[str, Any]]] = {name: [] for name in LIFECYCLE_HOOKS}
_LOADED_MODULES: list[ModuleType] = []


def clear_python_hooks() -> None:
    for hooks in _LIFECYCLE_HOOKS.values():
        hooks.clear()
    _LOADED_MODULES.clear()


def _import_file(module_name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _LOADED_MODULES.append(module)
    return module


def import_rules_module(mod: ModMetadata, filename: str) -> ModuleType | None:
    path = Path(mod.path) / "rules" / filename
    if not path.exists():
        return None
    safe_mod_id = mod.mod_id.replace("-", "_")
    return _import_file(f"cws_mod_{safe_mod_id}_rules_{path.stem}", path)


def register_lifecycle_hooks(mod: ModMetadata) -> None:
    code = (mod.extensions or {}).get("code") or {}
    declared = [str(item) for item in code.get("hooks", []) or []]
    if not declared:
        return
    module_path = Path(mod.path) / "code" / "lifecycle.py"
    if not module_path.exists():
        return
    module = _import_file(f"cws_mod_{mod.mod_id.replace('-', '_')}_lifecycle", module_path)
    for hook_name in declared:
        if hook_name not in LIFECYCLE_HOOKS:
            continue
        fn = getattr(module, hook_name, None)
        if callable(fn):
            _LIFECYCLE_HOOKS[hook_name].append((mod.mod_id, fn))


def dispatch_lifecycle_hook(hook_name: str, *args: Any, **kwargs: Any) -> None:
    for _, fn in list(_LIFECYCLE_HOOKS.get(hook_name, [])):
        fn(*args, **kwargs)


def get_lifecycle_hooks() -> dict[str, list[str]]:
    return {name: [mod_id for mod_id, _ in hooks] for name, hooks in _LIFECYCLE_HOOKS.items()}
