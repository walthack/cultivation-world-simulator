from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.config.presets import DEFAULT_PRESET_ID, get_active_preset_id, get_presets_root
from src.scenario.scenario_loader import KIND_TO_PRESET_FILE


class ScenarioSourceMissingError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SourceHandle:
    kind: str
    preset_id: str
    data: dict[str, Any]
    provenance: str
    path: Path | None = None


_ACTIVE_SCENARIO: Any | None = None
_ACTIVE_SCENARIO_EXPLICIT = False


def set_active_scenario_source(scenario: Any | None, *, explicit: bool = True) -> None:
    global _ACTIVE_SCENARIO, _ACTIVE_SCENARIO_EXPLICIT
    _ACTIVE_SCENARIO = scenario
    _ACTIVE_SCENARIO_EXPLICIT = bool(explicit)


def get_active_scenario_source() -> Any | None:
    return _ACTIVE_SCENARIO


def clear_active_scenario_source() -> None:
    set_active_scenario_source(None, explicit=False)


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ScenarioSourceMissingError(f"Preset source must be a JSON object: {path}")
    return data


def _preset_handle(kind: str, preset_id: str, *, provenance: str) -> SourceHandle:
    filename = KIND_TO_PRESET_FILE.get(kind)
    if filename is None:
        return SourceHandle(kind=kind, preset_id=preset_id, data={}, provenance=provenance, path=None)
    path = get_presets_root() / preset_id / filename
    if not path.exists():
        raise ScenarioSourceMissingError(f"Missing preset source for {kind}: {path}")
    return SourceHandle(kind=kind, preset_id=preset_id, data=_load_json(path), provenance=provenance, path=path)


def _default_handle(kind: str, *, provenance: str = "default") -> SourceHandle:
    return _preset_handle(kind, DEFAULT_PRESET_ID, provenance=provenance)


def resolve_source(kind: str, *, scenario: Any | None = None) -> SourceHandle:
    active_scenario = scenario if scenario is not None else _ACTIVE_SCENARIO
    if active_scenario is None:
        active_preset = get_active_preset_id()
        if active_preset and active_preset != DEFAULT_PRESET_ID and not _ACTIVE_SCENARIO_EXPLICIT:
            return _preset_handle(kind, active_preset, provenance=f"preset:{active_preset}")
        return _default_handle(kind)

    scenario_data = getattr(active_scenario, "scenario", active_scenario) or {}
    sources = scenario_data.get("generation_sources") if isinstance(scenario_data, dict) else None
    if not isinstance(sources, dict):
        return _default_handle(kind, provenance="default:v1.1-implicit")

    source = sources.get(kind)
    if source is None:
        return _default_handle(kind, provenance="default:source-omitted")
    if source == "default":
        return _default_handle(kind, provenance=f"default:{kind}")
    if source != "scenario":
        return _default_handle(kind, provenance=f"default:invalid-{kind}")

    preset_id = str(getattr(active_scenario, "preset_id", "") or "")
    if not preset_id and isinstance(scenario_data, dict):
        world_preset = scenario_data.get("world_preset") if isinstance(scenario_data.get("world_preset"), dict) else {}
        preset_id = str(world_preset.get("preset_id") or DEFAULT_PRESET_ID)
    fallback = bool(sources.get("fallback_to_default", False))
    filename = KIND_TO_PRESET_FILE.get(kind)
    if filename is None:
        return SourceHandle(kind=kind, preset_id=preset_id, data={}, provenance=f"scenario:{preset_id}", path=None)

    path = get_presets_root() / preset_id / filename
    if path.exists():
        return SourceHandle(
            kind=kind,
            preset_id=preset_id,
            data=_load_json(path),
            provenance=f"scenario:{preset_id}",
            path=path,
        )
    if fallback:
        return _default_handle(kind, provenance=f"default:fallback-missing-{preset_id}:{kind}")

    scenario_id = str(getattr(active_scenario, "scenario_id", "") or scenario_data.get("scenario_id") or "")
    raise ScenarioSourceMissingError(
        f"Scenario {scenario_id!r} declares generation_sources.{kind}='scenario' "
        f"but {path} is missing."
    )
