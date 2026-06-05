from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.config.presets import get_presets_root


@dataclass(slots=True)
class CompatResult:
    status: str
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


_SEMVER_RE = re.compile(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:-([0-9A-Za-z.-]+))?$")


def parse_lenient_semver(version: str | None) -> tuple[int, int, int, str | None] | None:
    match = _SEMVER_RE.match(str(version or "").strip())
    if match is None:
        return None
    major, minor, patch, prerelease = match.groups()
    return int(major), int(minor or 0), int(patch or 0), prerelease


def compare_lenient_semver(left: str | None, right: str | None) -> int | None:
    parsed_left = parse_lenient_semver(left)
    parsed_right = parse_lenient_semver(right)
    if parsed_left is None or parsed_right is None:
        return None
    left_core = parsed_left[:3]
    right_core = parsed_right[:3]
    if left_core != right_core:
        return 1 if left_core > right_core else -1
    left_pre = parsed_left[3]
    right_pre = parsed_right[3]
    if left_pre == right_pre:
        return 0
    if left_pre is None:
        return 1
    if right_pre is None:
        return -1
    return 1 if left_pre > right_pre else -1


def _schema_version_value(value: str | None) -> tuple[int, ...] | None:
    parts = str(value or "").strip().split(".")
    if not parts or any(not part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def _schema_greater(required: str, current: str) -> bool:
    required_parts = _schema_version_value(required)
    current_parts = _schema_version_value(current)
    if required_parts is None or current_parts is None:
        return str(required) > str(current)
    width = max(len(required_parts), len(current_parts))
    return required_parts + (0,) * (width - len(required_parts)) > current_parts + (0,) * (width - len(current_parts))


def _preset_exists(preset_id: str) -> bool:
    return (get_presets_root() / preset_id).is_dir()


def check_compatibility(
    scenario_dict: dict[str, Any],
    current_cws_version: str,
    current_schema_versions: set[str] | list[str] | tuple[str, ...],
) -> CompatResult:
    warnings: list[str] = []
    errors: list[str] = []
    current_schema = max((str(item) for item in current_schema_versions), default="0.1")

    engine = scenario_dict.get("engine")
    if engine is not None and not isinstance(engine, dict):
        errors.append("engine must be an object when present")
    elif isinstance(engine, dict):
        schema_min = engine.get("schema_version_min")
        if schema_min is not None and _schema_greater(str(schema_min), current_schema):
            errors.append(f"scenario requires schema_version_min {schema_min}, current max is {current_schema}")
        cws_min = engine.get("cws_version_min")
        if cws_min is not None:
            comparison = compare_lenient_semver(current_cws_version, str(cws_min))
            if comparison is not None and comparison < 0:
                warnings.append(f"scenario recommends CWS {cws_min} or newer, current is {current_cws_version}")

    dependencies = scenario_dict.get("dependencies", [])
    if dependencies is None:
        dependencies = []
    if not isinstance(dependencies, list):
        errors.append("dependencies must be a list when present")
    else:
        for idx, dependency in enumerate(dependencies):
            if not isinstance(dependency, dict):
                errors.append(f"dependencies[{idx}] must be an object")
                continue
            dep_type = dependency.get("type")
            dep_id = dependency.get("id")
            if dep_type != "preset":
                errors.append(f"dependencies[{idx}].type must be preset in v0.9")
                continue
            if not isinstance(dep_id, str) or not dep_id.strip():
                errors.append(f"dependencies[{idx}].id must be a non-empty string")
            elif not _preset_exists(dep_id):
                errors.append(f"missing preset dependency: {dep_id}")

    status = "fail" if errors else "warn" if warnings else "pass"
    return CompatResult(status=status, warnings=warnings, errors=errors)
