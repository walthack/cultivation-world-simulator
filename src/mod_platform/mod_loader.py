from __future__ import annotations

from pathlib import Path
from typing import Any

from src.config import get_settings_service
from src.scenario.condition_evaluator import register_predicate, reset_predicate_registry
from src.scenario.effect_applier import register_effect, reset_effect_registry

from .asset_overlay import configure_asset_overlay
from .llm_overlay import configure_llm_overlays
from .locale_overlay import configure_locale_overlays
from .mod_conflict import ModConflict, ModConflictError, detect_extension_conflicts, set_last_conflicts
from .mod_extension_points import ExtensionKind, iter_declared_extensions
from .mod_registry import ordered_mods
from .python_hooks import clear_python_hooks, import_rules_module, register_lifecycle_hooks


_ACTIVE_EXTENSIONS: list[dict[str, Any]] = []


def allow_trusted_python_mods(settings_view: Any | None = None) -> bool:
    if settings_view is None:
        settings_view = get_settings_service().get_settings_view()
    return bool(getattr(settings_view, "allow_trusted_python_mods", False))


def load_enabled_mods(*, settings_view: Any | None = None, bundled_assets_root: Path | str | None = None) -> dict[str, Any]:
    allow_python = allow_trusted_python_mods(settings_view)
    reset_predicate_registry()
    reset_effect_registry()
    clear_python_hooks()

    active_mods = ordered_mods(enabled_only=True)
    all_extensions = [extension for mod in active_mods for extension in iter_declared_extensions(mod)]
    python_extensions = [extension for extension in all_extensions if extension.python_required]
    data_extensions = [extension for extension in all_extensions if not extension.python_required]

    conflicts = detect_extension_conflicts(data_extensions + (python_extensions if allow_python else []))
    if conflicts:
        raise ModConflictError(conflicts)

    asset_dirs: list[Path] = []
    prompt_entries: list[tuple[str, Path]] = []
    locale_entries: list[tuple[str, Path, str]] = []

    for mod in active_mods:
        mod_dir = Path(mod.path)
        asset_dir = mod_dir / "assets"
        if asset_dir.exists():
            asset_dirs.append(asset_dir)
        extensions = mod.extensions or {}
        for item in (extensions.get("llm") or {}).get("prompts", []) or []:
            if isinstance(item, dict):
                prompt_entries.append((str(item.get("key", "")), mod_dir / str(item.get("template_path", ""))))
        localizations = ((extensions.get("assets") or {}).get("localizations") or {})
        if isinstance(localizations, dict):
            for locale_code, locale_path in localizations.items():
                locale_entries.append((str(locale_code), mod_dir / str(locale_path), mod.mod_id))

    configure_asset_overlay(asset_dirs, bundled_assets_root)
    configure_llm_overlays(prompt_entries)
    locale_conflicts = configure_locale_overlays(locale_entries)
    if locale_conflicts:
        conflicts = [
            ModConflict(kind="locale", name=f"{item['locale']}:{item['key']}", mod_ids=item["mod_ids"])
            for item in locale_conflicts
        ]
        set_last_conflicts(conflicts)
        raise ModConflictError(conflicts)

    for mod in active_mods:
        mod.python_hooks_enabled = bool(allow_python and mod.python_hooks_declared)
        if not allow_python:
            continue
        rules = mod.extensions.get("rules") or {}
        predicates_module = import_rules_module(mod, "predicates.py")
        if predicates_module is not None:
            for name in rules.get("predicates", []) or []:
                fn = getattr(predicates_module, str(name), None)
                if callable(fn):
                    register_predicate(str(name), fn, source=mod.mod_id)
        effects_module = import_rules_module(mod, "effects.py")
        if effects_module is not None:
            for name in rules.get("effects", []) or []:
                fn = getattr(effects_module, str(name), None)
                if callable(fn):
                    register_effect(str(name), fn, source=mod.mod_id)
        register_lifecycle_hooks(mod)

    global _ACTIVE_EXTENSIONS
    _ACTIVE_EXTENSIONS = [
        {
            **extension.to_dict(),
            "active": (not extension.python_required) or allow_python,
            "inert": extension.python_required and not allow_python,
        }
        for extension in all_extensions
    ]
    set_last_conflicts([])
    return {"mods": [mod.to_dict() for mod in active_mods], "extensions": list(_ACTIVE_EXTENSIONS)}


def get_active_extensions() -> list[dict[str, Any]]:
    return list(_ACTIVE_EXTENSIONS)


def refresh_mods_after_state_change(*, settings_view: Any | None = None, bundled_assets_root: Path | str | None = None) -> dict[str, Any]:
    return load_enabled_mods(settings_view=settings_view, bundled_assets_root=bundled_assets_root)
