from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .mod_extension_points import ModExtension


@dataclass(frozen=True)
class ModConflict:
    kind: str
    name: str
    mod_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "name": self.name, "mod_ids": self.mod_ids}


class ModConflictError(ValueError):
    def __init__(self, conflicts: list[ModConflict]):
        self.conflicts = conflicts
        super().__init__("Mod extension conflict")

    def to_dict(self) -> dict[str, Any]:
        return {"conflicts": [item.to_dict() for item in self.conflicts]}


_LAST_CONFLICTS: list[ModConflict] = []


def set_last_conflicts(conflicts: list[ModConflict]) -> None:
    global _LAST_CONFLICTS
    _LAST_CONFLICTS = list(conflicts)


def get_last_conflicts() -> list[dict[str, Any]]:
    return [item.to_dict() for item in _LAST_CONFLICTS]


def detect_extension_conflicts(extensions: list[ModExtension]) -> list[ModConflict]:
    seen: dict[tuple[str, str], list[str]] = {}
    for extension in extensions:
        key = (extension.kind.value, extension.name)
        seen.setdefault(key, [])
        if extension.mod_id not in seen[key]:
            seen[key].append(extension.mod_id)

    conflicts = [
        ModConflict(kind=kind, name=name, mod_ids=mod_ids)
        for (kind, name), mod_ids in seen.items()
        if len(mod_ids) > 1
    ]
    set_last_conflicts(conflicts)
    return conflicts
