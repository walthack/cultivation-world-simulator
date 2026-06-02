from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.config.presets import (
    get_preset_goldfinger_keys,
    get_preset_persona_keys,
    get_preset_realm_order,
    get_preset_sect_ids,
    get_presets_root,
    get_project_root,
)


SCHEMA_VERSION = "0.1"
SCENARIO_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
EVENT_TYPES = {
    "main",
    "world_event",
    "character_introduction",
    "relation_change",
    "relationship_event",
    "sect_event",
    "side_event",
    "ending",
}


class ScenarioValidationError(ValueError):
    def __init__(self, path: str, expected: str, actual: Any):
        self.path = path
        self.expected = expected
        self.actual = actual
        super().__init__(f"{path}: expected {expected}, got {actual!r}")


class MissingReferenceError(ScenarioValidationError):
    def __init__(self, path: str, reference: Any, suggestion: str = ""):
        expected = "known reference"
        if suggestion:
            expected += f" ({suggestion})"
        super().__init__(path, expected, reference)
        self.reference = reference
        self.suggestion = suggestion


@dataclass(slots=True)
class ResolvedScenario:
    scenario_id: str
    title: str
    version: str
    preset_id: str
    scenario: dict[str, Any]
    timeline: list[dict[str, Any]] = field(default_factory=list)
    scenario_dir: Path | None = None


def _load_json(path: Path, *, required: bool) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise ScenarioValidationError(str(path), "existing JSON file", "missing")
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ScenarioValidationError(str(path), "valid JSON", str(exc)) from exc
    if not isinstance(data, dict):
        raise ScenarioValidationError(str(path), "JSON object", type(data).__name__)
    return data


def _require(data: dict[str, Any], key: str, path: str) -> Any:
    if key not in data:
        raise ScenarioValidationError(f"{path}.{key}", "required field", "missing")
    return data[key]


def _validate_schema_version(data: dict[str, Any], path: str) -> None:
    actual = _require(data, "schema_version", path)
    if str(actual) != SCHEMA_VERSION:
        raise ScenarioValidationError(f"{path}.schema_version", SCHEMA_VERSION, actual)


def _validate_scenario_top_level(data: dict[str, Any]) -> str:
    _validate_schema_version(data, "scenario")
    scenario_id = _require(data, "scenario_id", "scenario")
    if not isinstance(scenario_id, str) or not SCENARIO_ID_RE.match(scenario_id):
        raise ScenarioValidationError("scenario.scenario_id", "snake_case scenario id", scenario_id)
    for key in ("title", "version"):
        value = _require(data, key, "scenario")
        if not isinstance(value, str) or not value.strip():
            raise ScenarioValidationError(f"scenario.{key}", "non-empty string", value)

    world_preset = _require(data, "world_preset", "scenario")
    if not isinstance(world_preset, dict):
        raise ScenarioValidationError("scenario.world_preset", "object", world_preset)
    preset_id = _require(world_preset, "preset_id", "scenario.world_preset")
    if not isinstance(preset_id, str) or "/" in preset_id or "\\" in preset_id or preset_id.startswith("."):
        raise ScenarioValidationError("scenario.world_preset.preset_id", "relative preset id", preset_id)
    if not (get_presets_root() / preset_id).is_dir():
        raise MissingReferenceError("scenario.world_preset.preset_id", preset_id, "config/presets/<preset_id>")
    return preset_id


def _validate_initial_state(data: dict[str, Any], preset_id: str) -> None:
    initial_state = data.get("initial_state", {})
    if initial_state is None:
        initial_state = {}
    if not isinstance(initial_state, dict):
        raise ScenarioValidationError("scenario.initial_state", "object", initial_state)

    avatar_ids: set[str] = set()
    sect_ids = set(get_preset_sect_ids(preset_id))
    realm_ids = set(get_preset_realm_order(preset_id))
    persona_keys = get_preset_persona_keys(preset_id)
    goldfinger_keys = get_preset_goldfinger_keys(preset_id)

    avatars = initial_state.get("avatars", [])
    if not isinstance(avatars, list):
        raise ScenarioValidationError("scenario.initial_state.avatars", "list", avatars)
    for idx, avatar in enumerate(avatars):
        path = f"scenario.initial_state.avatars[{idx}]"
        if not isinstance(avatar, dict):
            raise ScenarioValidationError(path, "object", avatar)
        avatar_id = _require(avatar, "id", path)
        if not isinstance(avatar_id, str) or not avatar_id.strip():
            raise ScenarioValidationError(f"{path}.id", "non-empty string", avatar_id)
        if avatar_id in avatar_ids:
            raise ScenarioValidationError(f"{path}.id", "unique avatar id", avatar_id)
        avatar_ids.add(avatar_id)

        sect_id = avatar.get("sect_id")
        if sect_id is not None and sect_id not in sect_ids:
            raise MissingReferenceError(f"{path}.sect_id", sect_id, "preset sects.json")
        realm = avatar.get("realm")
        if realm is not None and str(realm) not in realm_ids:
            raise MissingReferenceError(f"{path}.realm", realm, "preset realms.json")
        goldfinger_id = avatar.get("goldfinger_id")
        if goldfinger_id is not None and str(goldfinger_id).upper() not in goldfinger_keys:
            raise MissingReferenceError(f"{path}.goldfinger_id", goldfinger_id, "preset goldfingers.json")
        for trait in avatar.get("persona_traits", []) or []:
            if str(trait).upper() not in persona_keys:
                raise MissingReferenceError(f"{path}.persona_traits", trait, "preset personas.json")

    for idx, relation in enumerate(initial_state.get("relationships", []) or []):
        path = f"scenario.initial_state.relationships[{idx}]"
        for key in ("a", "b"):
            avatar_id = relation.get(key)
            if avatar_id not in avatar_ids:
                raise MissingReferenceError(f"{path}.{key}", avatar_id, "initial_state.avatars")

    for idx, sect in enumerate(initial_state.get("sects", []) or []):
        path = f"scenario.initial_state.sects[{idx}]"
        sect_id = _require(sect, "id", path)
        if sect_id not in sect_ids:
            raise MissingReferenceError(f"{path}.id", sect_id, "preset sects.json")
        leader_id = sect.get("leader_avatar_id")
        if leader_id is not None and leader_id not in avatar_ids:
            raise MissingReferenceError(f"{path}.leader_avatar_id", leader_id, "initial_state.avatars")
        for member_id in sect.get("member_avatar_ids", []) or []:
            if member_id not in avatar_ids:
                raise MissingReferenceError(f"{path}.member_avatar_ids", member_id, "initial_state.avatars")


def _validate_timeline(timeline_data: dict[str, Any]) -> list[dict[str, Any]]:
    if not timeline_data:
        return []
    _validate_schema_version(timeline_data, "timeline")
    events = timeline_data.get("events", [])
    if not isinstance(events, list):
        raise ScenarioValidationError("timeline.events", "list", events)
    event_ids: set[str] = set()
    for idx, event in enumerate(events):
        path = f"timeline.events[{idx}]"
        if not isinstance(event, dict):
            raise ScenarioValidationError(path, "object", event)
        event_id = _require(event, "id", path)
        if not isinstance(event_id, str) or not event_id.strip():
            raise ScenarioValidationError(f"{path}.id", "non-empty string", event_id)
        if event_id in event_ids:
            raise ScenarioValidationError(f"{path}.id", "unique event id", event_id)
        event_ids.add(event_id)
        event_type = _require(event, "type", path)
        if event_type not in EVENT_TYPES:
            raise ScenarioValidationError(f"{path}.type", f"one of {sorted(EVENT_TYPES)}", event_type)
        trigger = _require(event, "trigger", path)
        if not isinstance(trigger, dict):
            raise ScenarioValidationError(f"{path}.trigger", "object", trigger)
        for key in ("year", "month"):
            value = _require(trigger, key, f"{path}.trigger")
            if not isinstance(value, int):
                raise ScenarioValidationError(f"{path}.trigger.{key}", "integer", value)

    for idx, event in enumerate(events):
        path = f"timeline.events[{idx}]"
        for field_name in ("requires_events", "blocks_events"):
            for ref in event.get(field_name, []) or []:
                if ref not in event_ids:
                    raise MissingReferenceError(f"{path}.{field_name}", ref, "timeline.events[].id")
    return events


def load(scenario_id: str, *, scenarios_root: Path | None = None) -> ResolvedScenario:
    root = scenarios_root or (get_project_root() / "config" / "scenarios")
    scenario_dir = root / scenario_id
    scenario = _load_json(scenario_dir / "scenario.json", required=True)
    timeline_data = _load_json(scenario_dir / "timeline.json", required=False)
    preset_id = _validate_scenario_top_level(scenario)
    _validate_initial_state(scenario, preset_id)
    timeline = _validate_timeline(timeline_data)
    return ResolvedScenario(
        scenario_id=str(scenario["scenario_id"]),
        title=str(scenario["title"]),
        version=str(scenario["version"]),
        preset_id=preset_id,
        scenario=scenario,
        timeline=timeline,
        scenario_dir=scenario_dir,
    )
