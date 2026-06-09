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
    source: str = "default"


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
        return SourceHandle(
            kind=kind,
            preset_id=preset_id,
            data={},
            provenance=provenance,
            path=None,
            source="scenario" if provenance.startswith(("scenario:", "preset:")) else "default",
        )
    path = get_presets_root() / preset_id / filename
    if not path.exists():
        raise ScenarioSourceMissingError(f"Missing preset source for {kind}: {path}")
    return SourceHandle(
        kind=kind,
        preset_id=preset_id,
        data=_load_json(path),
        provenance=provenance,
        path=path,
        source="scenario" if provenance.startswith(("scenario:", "preset:")) else "default",
    )


def _default_handle(kind: str, *, provenance: str = "default") -> SourceHandle:
    return _preset_handle(kind, DEFAULT_PRESET_ID, provenance=provenance)


def _scenario_preset_id(active_scenario: Any, scenario_data: dict[str, Any]) -> str:
    preset_id = str(getattr(active_scenario, "preset_id", "") or "")
    if preset_id:
        return preset_id
    world_preset = scenario_data.get("world_preset")
    if not isinstance(world_preset, dict):
        return DEFAULT_PRESET_ID
    return str(world_preset.get("preset_id") or DEFAULT_PRESET_ID)


def _profile_source(scenario_data: dict[str, Any], kind: str) -> str | None:
    initial_state = scenario_data.get("initial_state")
    if not isinstance(initial_state, dict):
        return None
    profile = initial_state.get("generation_profile")
    if not isinstance(profile, dict):
        return None
    sources = profile.get("generation_sources")
    if not isinstance(sources, dict):
        return None
    source = sources.get(kind)
    return str(source) if source is not None else None


def _item_identity(item: object) -> tuple[str, str]:
    if isinstance(item, dict):
        for key in ("id", "key", "name"):
            value = item.get(key)
            if value is not None:
                return "value", str(value)
        return "dict", json.dumps(item, ensure_ascii=False, sort_keys=True)
    return "value", str(item)


def _scenario_first_list(scenario_items: list[Any], default_items: list[Any]) -> list[Any]:
    merged: list[Any] = []
    seen: set[tuple[str, str]] = set()
    for item in [*scenario_items, *default_items]:
        identity = _item_identity(item)
        if identity in seen:
            continue
        seen.add(identity)
        merged.append(item)
    return merged


def _merge_source_data(kind: str, scenario_data: dict[str, Any], default_data: dict[str, Any]) -> dict[str, Any]:
    if kind == "npc_names":
        return {
            **default_data,
            **scenario_data,
            "mode": "mixed",
        }
    if kind == "personas":
        scenario_items = scenario_data.get("personas") or scenario_data.get("persona_keys") or []
        default_items = default_data.get("personas") or default_data.get("persona_keys") or []
        return {
            **default_data,
            **scenario_data,
            "personas": _scenario_first_list(list(scenario_items), list(default_items)),
        }

    merged = dict(default_data)
    for key, value in scenario_data.items():
        if isinstance(value, list) and isinstance(default_data.get(key), list):
            merged[key] = _scenario_first_list(value, default_data[key])
        elif isinstance(value, dict) and isinstance(default_data.get(key), dict):
            merged[key] = {**default_data[key], **value}
        else:
            merged[key] = value
    return merged


def _mixed_handle(kind: str, preset_id: str) -> SourceHandle:
    scenario_handle = _preset_handle(kind, preset_id, provenance=f"scenario:{preset_id}")
    default_handle = _default_handle(kind)
    return SourceHandle(
        kind=kind,
        preset_id=preset_id,
        data=_merge_source_data(kind, scenario_handle.data, default_handle.data),
        provenance=f"mixed:{preset_id}+default",
        path=scenario_handle.path,
        source="mixed",
    )


def resolve_source(kind: str, *, scenario: Any | None = None) -> SourceHandle:
    active_scenario = scenario if scenario is not None else _ACTIVE_SCENARIO
    if active_scenario is None:
        active_preset = get_active_preset_id()
        if active_preset and active_preset != DEFAULT_PRESET_ID and not _ACTIVE_SCENARIO_EXPLICIT:
            return _preset_handle(kind, active_preset, provenance=f"preset:{active_preset}")
        return _default_handle(kind)

    scenario_data = getattr(active_scenario, "scenario", active_scenario) or {}
    if not isinstance(scenario_data, dict):
        return _default_handle(kind, provenance="default:invalid-scenario")

    preset_id = _scenario_preset_id(active_scenario, scenario_data)
    sources = scenario_data.get("generation_sources") if isinstance(scenario_data, dict) else None
    profile_source = _profile_source(scenario_data, kind)
    # Persona sampling keeps the schema-v1.2 top-level source contract authoritative.
    if kind == "personas" and isinstance(sources, dict) and kind in sources:
        profile_source = None
    if profile_source == "default":
        return _default_handle(kind, provenance=f"default:profile-{kind}")
    if profile_source == "scenario":
        return _preset_handle(kind, preset_id, provenance=f"scenario:{preset_id}")
    if profile_source == "mixed":
        return _mixed_handle(kind, preset_id)

    if not isinstance(sources, dict):
        return _default_handle(kind, provenance="default:v1.1-implicit")

    source = sources.get(kind)
    if source is None:
        return _default_handle(kind, provenance="default:source-omitted")
    if source == "default":
        return _default_handle(kind, provenance=f"default:{kind}")
    if source != "scenario":
        return _default_handle(kind, provenance=f"default:invalid-{kind}")

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
            source="scenario",
        )
    if fallback:
        return _default_handle(kind, provenance=f"default:fallback-missing-{preset_id}:{kind}")

    scenario_id = str(getattr(active_scenario, "scenario_id", "") or scenario_data.get("scenario_id") or "")
    raise ScenarioSourceMissingError(
        f"Scenario {scenario_id!r} declares generation_sources.{kind}='scenario' "
        f"but {path} is missing."
    )
