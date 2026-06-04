from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class ExtensionKind(str, Enum):
    ASSET = "asset"
    LLM_PROMPT = "llm_prompt"
    LOCALE = "locale"
    PREDICATE = "predicate"
    EFFECT = "effect"
    LIFECYCLE_HOOK = "lifecycle_hook"


DATA_ONLY_KINDS = {
    ExtensionKind.ASSET,
    ExtensionKind.LLM_PROMPT,
    ExtensionKind.LOCALE,
}

PYTHON_KINDS = {
    ExtensionKind.PREDICATE,
    ExtensionKind.EFFECT,
    ExtensionKind.LIFECYCLE_HOOK,
}

LIFECYCLE_HOOKS = {
    "on_world_init",
    "on_step",
    "on_avatar_death",
    "on_scenario_event_dispatched",
}

PredicateFn = Callable[[Any, dict[str, Any]], bool]
EffectFn = Callable[[Any, dict[str, Any]], None]
LifecycleHookFn = Callable[..., None]


@dataclass(frozen=True)
class ModExtension:
    kind: ExtensionKind
    name: str
    mod_id: str
    path: str | None = None
    python_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "name": self.name,
            "mod_id": self.mod_id,
            "path": self.path,
            "python_required": self.python_required,
            "category": "python" if self.python_required else "data-only",
        }


@dataclass
class ModMetadata:
    mod_id: str
    name: str
    version: str
    author: str = ""
    description: str = ""
    fingerprint: str = ""
    dependencies: list[dict[str, Any]] = field(default_factory=list)
    extensions: dict[str, Any] = field(default_factory=dict)
    path: str = ""
    enabled: bool = True
    python_hooks_enabled: bool = False
    python_hooks_declared: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "mod_id": self.mod_id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "fingerprint": self.fingerprint,
            "dependencies": self.dependencies,
            "extensions": self.extensions,
            "path": self.path,
            "enabled": self.enabled,
            "python_hooks_enabled": self.python_hooks_enabled,
            "python_hooks_declared": self.python_hooks_declared,
        }


def iter_declared_extensions(metadata: ModMetadata) -> list[ModExtension]:
    extensions = metadata.extensions or {}
    declared: list[ModExtension] = []

    assets = extensions.get("assets") or {}
    for group in ("portraits", "icons"):
        for item in assets.get(group, []) or []:
            declared.append(ModExtension(ExtensionKind.ASSET, str(item), metadata.mod_id, str(item)))
    localizations = assets.get("localizations") or {}
    if isinstance(localizations, dict):
        for locale_code, locale_path in localizations.items():
            declared.append(ModExtension(ExtensionKind.LOCALE, str(locale_code), metadata.mod_id, str(locale_path)))

    llm = extensions.get("llm") or {}
    for item in llm.get("prompts", []) or []:
        if isinstance(item, dict):
            declared.append(
                ModExtension(
                    ExtensionKind.LLM_PROMPT,
                    str(item.get("key", "")),
                    metadata.mod_id,
                    str(item.get("template_path", "")),
                )
            )

    rules = extensions.get("rules") or {}
    for name in rules.get("predicates", []) or []:
        declared.append(ModExtension(ExtensionKind.PREDICATE, str(name), metadata.mod_id, python_required=True))
    for name in rules.get("effects", []) or []:
        declared.append(ModExtension(ExtensionKind.EFFECT, str(name), metadata.mod_id, python_required=True))

    code = extensions.get("code") or {}
    for name in code.get("hooks", []) or []:
        declared.append(ModExtension(ExtensionKind.LIFECYCLE_HOOK, str(name), metadata.mod_id, python_required=True))

    return [item for item in declared if item.name]


def mod_declares_python(metadata: ModMetadata) -> bool:
    return any(item.python_required for item in iter_declared_extensions(metadata))
