from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.config.presets import (
    get_preset_dynasty_ids,
    get_preset_goldfinger_keys,
    get_preset_orthodoxy_ids,
    get_preset_persona_keys,
    get_preset_race_ids,
    get_preset_realm_order,
    get_preset_region_ids,
    get_preset_root_ids,
    get_preset_sect_ids,
    get_preset_technique_ids,
    get_preset_weapon_ids,
    get_presets_root,
    get_project_root,
)


SCHEMA_VERSION = "0.1"
SUPPORTED_SCHEMA_VERSIONS = {"0.1", "0.2", "1.0", "1.1", "1.2"}
SCENARIO_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
SEMVER_RE = re.compile(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:-([0-9A-Za-z.-]+))?$")
GENERATION_SOURCE_VALUES = {"scenario", "default"}
GENERATION_PROFILE_SOURCE_VALUES = {"scenario", "default", "mixed"}
GENERATION_PROFILE_SOURCE_KEYS = ("npc_names", "personas", "sects", "regions")
NARRATIVE_CONTEXT_KEYS = ("background", "style", "terminology")
# Scenario generation source control v1.2, spec §5.1.
KIND_TO_PRESET_FILE = {
    "regions": "regions.json",
    "dynasties": "dynasties.json",
    "sects": "sects.json",
    "npc_names": "name_templates.json",
    "personas": "personas.json",
    "weapons": "weapons.json",
    "techniques": "techniques.json",
    "roots": "roots.json",
    "relations": None,
    "initial_events": None,
}
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
LOGGER = logging.getLogger(__name__)


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

    @property
    def generation_profile(self) -> dict[str, Any]:
        initial_state = self.scenario.get("initial_state", {}) or {}
        return dict(initial_state.get("generation_profile", {}) or {})


@dataclass(slots=True)
class ScenarioDirectoryValidationResult:
    scenario_id: str
    title: str
    version: str
    preset_id: str
    warnings: list[str] = field(default_factory=list)


def parse_lenient_semver(version: str | None) -> tuple[int, int, int, str | None] | None:
    match = SEMVER_RE.match(str(version or "").strip())
    if match is None:
        return None
    major, minor, patch, prerelease = match.groups()
    return int(major), int(minor or 0), int(patch or 0), prerelease


def compare_lenient_semver(left: str | None, right: str | None) -> int | None:
    parsed_left = parse_lenient_semver(left)
    parsed_right = parse_lenient_semver(right)
    if parsed_left is None or parsed_right is None:
        return None
    if parsed_left[:3] != parsed_right[:3]:
        return 1 if parsed_left[:3] > parsed_right[:3] else -1
    left_pre = parsed_left[3]
    right_pre = parsed_right[3]
    if left_pre == right_pre:
        return 0
    if left_pre is None:
        return 1
    if right_pre is None:
        return -1
    return 1 if left_pre > right_pre else -1


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


def _schema_version(data: dict[str, Any], path: str) -> str:
    actual = _require(data, "schema_version", path)
    normalized = str(actual)
    if normalized not in SUPPORTED_SCHEMA_VERSIONS:
        raise ScenarioValidationError(f"{path}.schema_version", f"one of {sorted(SUPPORTED_SCHEMA_VERSIONS)}", actual)
    return normalized


def _validate_schema_version(data: dict[str, Any], path: str) -> None:
    _schema_version(data, path)


def _validate_scenario_top_level(data: dict[str, Any]) -> str:
    _schema_version(data, "scenario")
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
    _validate_optional_metadata(data)
    return preset_id


def _validate_optional_metadata(data: dict[str, Any]) -> None:
    fingerprint = data.get("fingerprint")
    if fingerprint is not None and (not isinstance(fingerprint, str) or not fingerprint.startswith("sha256:")):
        raise ScenarioValidationError("scenario.fingerprint", "sha256 fingerprint string", fingerprint)

    engine = data.get("engine")
    if engine is not None:
        if not isinstance(engine, dict):
            raise ScenarioValidationError("scenario.engine", "object", engine)
        for key in ("schema_version_min", "cws_version_min"):
            value = engine.get(key)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ScenarioValidationError(f"scenario.engine.{key}", "non-empty string", value)

    dependencies = data.get("dependencies", [])
    if dependencies is None:
        return
    if not isinstance(dependencies, list):
        raise ScenarioValidationError("scenario.dependencies", "list", dependencies)
    for idx, dependency in enumerate(dependencies):
        path = f"scenario.dependencies[{idx}]"
        if not isinstance(dependency, dict):
            raise ScenarioValidationError(path, "object", dependency)
        dep_type = dependency.get("type")
        if dep_type not in {"preset", "mod"}:
            raise ScenarioValidationError(f"{path}.type", "preset or mod", dep_type)
        dep_id = dependency.get("id")
        if not isinstance(dep_id, str) or not dep_id.strip():
            raise ScenarioValidationError(f"{path}.id", "non-empty string", dep_id)
        version_req = dependency.get("version_req")
        if version_req is not None and not isinstance(version_req, str):
            raise ScenarioValidationError(f"{path}.version_req", "string", version_req)


def _is_v02(data: dict[str, Any]) -> bool:
    return str(data.get("schema_version")) in {"0.2", "1.1"}


def _validate_optional_generation_profile(initial_state: dict[str, Any]) -> None:
    profile = initial_state.get("generation_profile")
    if profile is None:
        return
    if not isinstance(profile, dict):
        raise ScenarioValidationError("scenario.initial_state.generation_profile", "object", profile)

    for key in ("random_npc_count", "random_sect_count"):
        value = profile.get(key)
        if value is None:
            continue
        if type(value) is not int or value < 0:
            raise ScenarioValidationError(
                f"scenario.initial_state.generation_profile.{key}",
                "integer >= 0",
                value,
            )

    value = profile.get("use_scripted_only")
    if value is not None and not isinstance(value, bool):
        raise ScenarioValidationError(
            "scenario.initial_state.generation_profile.use_scripted_only",
            "boolean",
            value,
        )

    generation_sources = profile.get("generation_sources")
    if generation_sources is not None:
        if not isinstance(generation_sources, dict):
            raise ScenarioValidationError(
                "scenario.initial_state.generation_profile.generation_sources",
                "object",
                generation_sources,
            )
        unknown_keys = set(generation_sources) - set(GENERATION_PROFILE_SOURCE_KEYS)
        if unknown_keys:
            key = sorted(unknown_keys)[0]
            raise ScenarioValidationError(
                f"scenario.initial_state.generation_profile.generation_sources.{key}",
                f"one of {sorted(GENERATION_PROFILE_SOURCE_KEYS)}",
                generation_sources[key],
            )
        for key in GENERATION_PROFILE_SOURCE_KEYS:
            source = generation_sources.get(key)
            if source is not None and source not in GENERATION_PROFILE_SOURCE_VALUES:
                raise ScenarioValidationError(
                    f"scenario.initial_state.generation_profile.generation_sources.{key}",
                    "scenario, default, or mixed",
                    source,
                )

    narrative_context = profile.get("narrative_context")
    if narrative_context is not None:
        if not isinstance(narrative_context, dict):
            raise ScenarioValidationError(
                "scenario.initial_state.generation_profile.narrative_context",
                "object",
                narrative_context,
            )
        unknown_keys = set(narrative_context) - set(NARRATIVE_CONTEXT_KEYS)
        if unknown_keys:
            key = sorted(unknown_keys)[0]
            raise ScenarioValidationError(
                f"scenario.initial_state.generation_profile.narrative_context.{key}",
                f"one of {sorted(NARRATIVE_CONTEXT_KEYS)}",
                narrative_context[key],
            )
        for key in NARRATIVE_CONTEXT_KEYS:
            context_value = narrative_context.get(key)
            if context_value is not None and not isinstance(context_value, str):
                raise ScenarioValidationError(
                    f"scenario.initial_state.generation_profile.narrative_context.{key}",
                    "string",
                    context_value,
                )


def _validate_generation_sources(data: dict[str, Any], *, preset_id: str) -> None:
    sources = data.get("generation_sources")
    if sources is None:
        return
    if not isinstance(sources, dict):
        raise ScenarioValidationError("scenario.generation_sources", "object", sources)

    fallback = sources.get("fallback_to_default", False)
    if not isinstance(fallback, bool):
        raise ScenarioValidationError(
            "scenario.generation_sources.fallback_to_default",
            "boolean",
            fallback,
        )

    scenario_id = str(data.get("scenario_id") or "")
    preset_root = get_presets_root() / preset_id
    for key, value in sources.items():
        if key == "fallback_to_default":
            continue
        if key not in KIND_TO_PRESET_FILE:
            LOGGER.warning("Unknown scenario generation_sources key ignored: %s", key)
            continue
        if value not in GENERATION_SOURCE_VALUES:
            raise ScenarioValidationError(
                f"scenario.generation_sources.{key}",
                "scenario or default",
                value,
            )
        filename = KIND_TO_PRESET_FILE[key]
        if value != "scenario" or filename is None:
            continue
        expected_path = preset_root / filename
        if not expected_path.exists() and not fallback:
            raise ScenarioValidationError(
                f"scenario.generation_sources.{key}",
                (
                    f"existing preset file for scenario {scenario_id!r} "
                    f"at {expected_path}"
                ),
                "missing",
            )


def _warn_if_random_sect_count_exceeds_pool(data: dict[str, Any], *, preset_id: str) -> None:
    sources = data.get("generation_sources")
    if not isinstance(sources, dict) or sources.get("sects") != "scenario":
        return

    initial_state = data.get("initial_state", {}) or {}
    if not isinstance(initial_state, dict):
        return
    profile = initial_state.get("generation_profile") or {}
    if not isinstance(profile, dict):
        return

    random_sect_count = profile.get("random_sect_count")
    if type(random_sect_count) is not int or random_sect_count <= 0:
        return

    preset_sects = _load_json(get_presets_root() / preset_id / "sects.json", required=False)
    pool_size = len(preset_sects.get("sects", []) or [])
    scripted_count = len(initial_state.get("sects", []) or [])
    available = max(0, pool_size - scripted_count)
    if random_sect_count <= available:
        return

    scenario_id = str(data.get("scenario_id") or "")
    LOGGER.warning(
        "Scenario %r declared random_sect_count=%s but available_count=%s after "
        "scripted_count=%s from preset %r sect pool. effective_cap=%s.",
        scenario_id,
        random_sect_count,
        available,
        scripted_count,
        preset_id,
        available,
    )


def _validate_optional_avatar_placement(avatar: dict[str, Any], path: str) -> None:
    has_pos = avatar.get("pos") is not None
    has_region_id = avatar.get("region_id") is not None
    if has_pos and has_region_id:
        raise ScenarioValidationError(f"{path}.pos", "mutually exclusive with region_id", avatar.get("pos"))

    if has_pos:
        pos = avatar.get("pos")
        if not isinstance(pos, dict):
            raise ScenarioValidationError(f"{path}.pos", "object", pos)
        for key in ("x", "y"):
            value = pos.get(key)
            if type(value) is not int or value < 0:
                raise ScenarioValidationError(f"{path}.pos.{key}", "integer >= 0", value)

    if has_region_id:
        region_id = avatar.get("region_id")
        if type(region_id) is not int:
            raise ScenarioValidationError(f"{path}.region_id", "integer", region_id)


def _persona_trait_id(trait: Any) -> str:
    if isinstance(trait, dict):
        trait = trait.get("id")
    return str(trait).upper()


def _validate_persona_trait(trait: Any, path: str) -> str:
    if isinstance(trait, str):
        return trait
    if not isinstance(trait, dict):
        raise ScenarioValidationError(path, "persona id string or object", trait)
    trait_id = trait.get("id")
    if not isinstance(trait_id, str) or not trait_id.strip():
        raise ScenarioValidationError(f"{path}.id", "non-empty string", trait_id)
    stat_modifiers = trait.get("stat_modifiers", {})
    if stat_modifiers is not None and not isinstance(stat_modifiers, dict):
        raise ScenarioValidationError(f"{path}.stat_modifiers", "object", stat_modifiers)
    tags = trait.get("tags", [])
    if tags is not None and (not isinstance(tags, list) or not all(isinstance(item, str) for item in tags)):
        raise ScenarioValidationError(f"{path}.tags", "list[str]", tags)
    return trait_id


def _validate_goldfinger_model(value: Any, path: str) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        raise ScenarioValidationError(path, "goldfinger id string or object", value)
    goldfinger_id = value.get("id")
    if not isinstance(goldfinger_id, str) or not goldfinger_id.strip():
        raise ScenarioValidationError(f"{path}.id", "non-empty string", goldfinger_id)
    for field_name in ("side_effects", "synergies"):
        entries = value.get(field_name, [])
        if entries is not None and not isinstance(entries, list):
            raise ScenarioValidationError(f"{path}.{field_name}", "list", entries)
        for idx, entry in enumerate(entries or []):
            if not isinstance(entry, dict):
                raise ScenarioValidationError(f"{path}.{field_name}[{idx}]", "object", entry)
    patch = value.get("initial_state_patch", {})
    if patch is not None and not isinstance(patch, dict):
        raise ScenarioValidationError(f"{path}.initial_state_patch", "object", patch)
    return goldfinger_id


def _validate_avatar_techniques(avatar: dict[str, Any], path: str, technique_ids: set[str]) -> None:
    techniques = avatar.get("techniques", [])
    if techniques is None:
        return
    if not isinstance(techniques, list):
        raise ScenarioValidationError(f"{path}.techniques", "list", techniques)
    for idx, entry in enumerate(techniques):
        entry_path = f"{path}.techniques[{idx}]"
        if not isinstance(entry, dict):
            raise ScenarioValidationError(entry_path, "object", entry)
        technique_id = entry.get("technique_id")
        if str(technique_id) not in technique_ids:
            raise MissingReferenceError(f"{entry_path}.technique_id", technique_id, "preset techniques.json")
        level = entry.get("level", 1)
        if not isinstance(level, int) or level < 1:
            raise ScenarioValidationError(f"{entry_path}.level", "positive integer", level)


def _validate_avatar_weapons(avatar: dict[str, Any], path: str, weapon_ids: set[str]) -> None:
    weapons = avatar.get("weapons", [])
    if weapons is None:
        return
    if not isinstance(weapons, list):
        raise ScenarioValidationError(f"{path}.weapons", "list", weapons)
    for idx, entry in enumerate(weapons):
        entry_path = f"{path}.weapons[{idx}]"
        if not isinstance(entry, dict):
            raise ScenarioValidationError(entry_path, "object", entry)
        weapon_id = entry.get("weapon_id")
        if str(weapon_id) not in weapon_ids:
            raise MissingReferenceError(f"{entry_path}.weapon_id", weapon_id, "preset weapons.json")
        quantity = entry.get("quantity", 1)
        if not isinstance(quantity, int) or quantity < 1:
            raise ScenarioValidationError(f"{entry_path}.quantity", "positive integer", quantity)


def _validate_dynasty_entries(
    dynasties: Any,
    path: str,
    *,
    avatar_ids: set[str],
    dynasty_ids: set[str],
    region_ids: set[str],
    orthodoxy_ids: set[str],
) -> set[str]:
    if dynasties is None:
        return set()
    if not isinstance(dynasties, list):
        raise ScenarioValidationError(path, "list", dynasties)

    scenario_dynasty_ids: set[str] = set()
    for idx, dynasty in enumerate(dynasties):
        entry_path = f"{path}[{idx}]"
        if not isinstance(dynasty, dict):
            raise ScenarioValidationError(entry_path, "object", dynasty)
        dynasty_id = _require(dynasty, "id", entry_path)
        if not isinstance(dynasty_id, str) or not dynasty_id.strip():
            raise ScenarioValidationError(f"{entry_path}.id", "non-empty string", dynasty_id)
        if dynasty_id in scenario_dynasty_ids:
            raise ScenarioValidationError(f"{entry_path}.id", "unique dynasty id", dynasty_id)
        scenario_dynasty_ids.add(dynasty_id)

        status = dynasty.get("status", "active")
        if status not in {"active", "declining", "fallen"}:
            raise ScenarioValidationError(f"{entry_path}.status", "active | declining | fallen", status)
        founding_year = dynasty.get("founding_year", 1)
        if not isinstance(founding_year, (int, float)):
            raise ScenarioValidationError(f"{entry_path}.founding_year", "number", founding_year)
        ruler_avatar_id = dynasty.get("ruler_avatar_id")
        if ruler_avatar_id is not None and ruler_avatar_id not in avatar_ids:
            raise MissingReferenceError(f"{entry_path}.ruler_avatar_id", ruler_avatar_id, "initial_state.avatars")
        capital_region_id = dynasty.get("capital_region_id")
        if capital_region_id is not None and str(capital_region_id) not in region_ids:
            raise MissingReferenceError(f"{entry_path}.capital_region_id", capital_region_id, "preset regions.json")
        territory_region_ids = dynasty.get("territory_region_ids", [])
        if not isinstance(territory_region_ids, list):
            raise ScenarioValidationError(f"{entry_path}.territory_region_ids", "list", territory_region_ids)
        for region_id in territory_region_ids:
            if str(region_id) not in region_ids:
                raise MissingReferenceError(f"{entry_path}.territory_region_ids", region_id, "preset regions.json")
        for orthodoxy_id in dynasty.get("orthodoxy_ids", []) or []:
            if str(orthodoxy_id) not in orthodoxy_ids:
                raise MissingReferenceError(f"{entry_path}.orthodoxy_ids", orthodoxy_id, "preset orthodoxies.json")
        relations = dynasty.get("relations", [])
        if not isinstance(relations, list):
            raise ScenarioValidationError(f"{entry_path}.relations", "list", relations)
        for rel_idx, relation in enumerate(relations):
            rel_path = f"{entry_path}.relations[{rel_idx}]"
            if not isinstance(relation, dict):
                raise ScenarioValidationError(rel_path, "object", relation)
            relation_type = relation.get("type")
            if relation_type not in {"ally", "rival", "vassal", "enemy", "neutral"}:
                raise ScenarioValidationError(f"{rel_path}.type", "ally | rival | vassal | enemy | neutral", relation_type)
            value = relation.get("value")
            if not isinstance(value, (int, float)) or not -100 <= float(value) <= 100:
                raise ScenarioValidationError(f"{rel_path}.value", "number -100..100", value)

    known_dynasty_ids = dynasty_ids | scenario_dynasty_ids
    for idx, dynasty in enumerate(dynasties):
        entry_path = f"{path}[{idx}]"
        for rel_idx, relation in enumerate(dynasty.get("relations", []) or []):
            other_id = relation.get("other_dynasty_id")
            if str(other_id) not in known_dynasty_ids:
                raise MissingReferenceError(
                    f"{entry_path}.relations[{rel_idx}].other_dynasty_id",
                    other_id,
                    "preset/scenario dynasties",
                )
    return scenario_dynasty_ids


def _validate_initial_state(data: dict[str, Any], preset_id: str) -> None:
    initial_state = data.get("initial_state", {})
    if initial_state is None:
        initial_state = {}
    if not isinstance(initial_state, dict):
        raise ScenarioValidationError("scenario.initial_state", "object", initial_state)
    _validate_optional_generation_profile(initial_state)

    avatars = initial_state.get("avatars", [])
    if not isinstance(avatars, list):
        raise ScenarioValidationError("scenario.initial_state.avatars", "list", avatars)
    sects = initial_state.get("sects", []) or []
    dynasties = initial_state.get("dynasties")
    uses_v02 = _is_v02(data)
    needs_race_ids = uses_v02 and any(isinstance(avatar, dict) and avatar.get("race_id") is not None for avatar in avatars)
    needs_root_ids = uses_v02 and any(isinstance(avatar, dict) and avatar.get("root_id") is not None for avatar in avatars)
    needs_technique_ids = uses_v02 and any(isinstance(avatar, dict) and avatar.get("techniques") for avatar in avatars)
    needs_weapon_ids = uses_v02 and any(isinstance(avatar, dict) and avatar.get("weapons") for avatar in avatars)
    region_refs_present = (
        uses_v02
        and (
            any(isinstance(avatar, dict) and avatar.get("location_region_id") is not None for avatar in avatars)
            or any(isinstance(sect, dict) and sect.get("headquarters_region_id") is not None for sect in sects)
            or (
                isinstance(dynasties, list)
                and any(
                    isinstance(item, dict)
                    and (
                        item.get("capital_region_id") is not None
                        or bool(item.get("territory_region_ids", []) or [])
                    )
                    for item in dynasties
                )
            )
        )
    )

    avatar_ids: set[str] = set()
    sect_ids = set(get_preset_sect_ids(preset_id))
    realm_ids = set(get_preset_realm_order(preset_id))
    persona_keys = get_preset_persona_keys(preset_id)
    goldfinger_keys = get_preset_goldfinger_keys(preset_id)
    race_ids = get_preset_race_ids(preset_id) if needs_race_ids else set()
    root_ids = get_preset_root_ids(preset_id) if needs_root_ids else set()
    technique_ids = get_preset_technique_ids(preset_id) if needs_technique_ids else set()
    weapon_ids = get_preset_weapon_ids(preset_id) if needs_weapon_ids else set()
    region_ids = get_preset_region_ids(preset_id) if region_refs_present else set()
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
        _validate_optional_avatar_placement(avatar, path)

        sect_id = avatar.get("sect_id")
        if sect_id is not None and sect_id not in sect_ids:
            raise MissingReferenceError(f"{path}.sect_id", sect_id, "preset sects.json")
        realm = avatar.get("realm")
        if realm is not None and str(realm) not in realm_ids:
            raise MissingReferenceError(f"{path}.realm", realm, "preset realms.json")
        if uses_v02:
            race_id = avatar.get("race_id")
            if race_id is not None and str(race_id) not in race_ids:
                raise MissingReferenceError(f"{path}.race_id", race_id, "preset races.json")
            root_id = avatar.get("root_id")
            if root_id is not None and str(root_id).upper() not in root_ids:
                raise MissingReferenceError(f"{path}.root_id", root_id, "preset roots.json")
            location_region_id = avatar.get("location_region_id")
            if location_region_id is not None and str(location_region_id) not in region_ids:
                raise MissingReferenceError(f"{path}.location_region_id", location_region_id, "preset regions.json")
        goldfinger_id = avatar.get("goldfinger_id")
        if goldfinger_id is not None:
            resolved_goldfinger_id = (
                _validate_goldfinger_model(goldfinger_id, f"{path}.goldfinger_id")
                if uses_v02
                else str(goldfinger_id)
            )
            if str(resolved_goldfinger_id).upper() not in goldfinger_keys:
                raise MissingReferenceError(f"{path}.goldfinger_id", resolved_goldfinger_id, "preset goldfingers.json")
        for trait_idx, trait in enumerate(avatar.get("persona_traits", []) or []):
            resolved_trait = (
                _validate_persona_trait(trait, f"{path}.persona_traits[{trait_idx}]")
                if uses_v02
                else _persona_trait_id(trait)
            )
            if str(resolved_trait).upper() not in persona_keys:
                raise MissingReferenceError(f"{path}.persona_traits", trait, "preset personas.json")
        if uses_v02:
            _validate_avatar_techniques(avatar, path, technique_ids)
            _validate_avatar_weapons(avatar, path, weapon_ids)

    for idx, relation in enumerate(initial_state.get("relationships", []) or []):
        path = f"scenario.initial_state.relationships[{idx}]"
        for key in ("a", "b"):
            avatar_id = relation.get(key)
            if avatar_id not in avatar_ids:
                raise MissingReferenceError(f"{path}.{key}", avatar_id, "initial_state.avatars")

    for idx, sect in enumerate(sects):
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
        if uses_v02:
            headquarters_region_id = sect.get("headquarters_region_id")
            if headquarters_region_id is not None and str(headquarters_region_id) not in region_ids:
                raise MissingReferenceError(f"{path}.headquarters_region_id", headquarters_region_id, "preset regions.json")

    if uses_v02 and "dynasties" in initial_state:
        dynasty_entries = initial_state.get("dynasties")
        orthodoxy_refs_present = (
            isinstance(dynasty_entries, list)
            and any(isinstance(item, dict) and bool(item.get("orthodoxy_ids", []) or []) for item in dynasty_entries)
        )
        _validate_dynasty_entries(
            dynasty_entries,
            "scenario.initial_state.dynasties",
            avatar_ids=avatar_ids,
            dynasty_ids=get_preset_dynasty_ids(preset_id),
            region_ids=region_ids if region_refs_present else set(),
            orthodoxy_ids=get_preset_orthodoxy_ids(preset_id) if orthodoxy_refs_present else set(),
        )


def _validate_timeline(timeline_data: dict[str, Any], *, preset_id: str, scenario_schema_version: str) -> list[dict[str, Any]]:
    if not timeline_data:
        return []
    timeline_schema_version = _schema_version(timeline_data, "timeline")
    events = timeline_data.get("events", [])
    if not isinstance(events, list):
        raise ScenarioValidationError("timeline.events", "list", events)
    event_ids: set[str] = set()
    uses_v02_timeline = scenario_schema_version == "0.2" or timeline_schema_version == "0.2"
    region_ids = get_preset_region_ids(preset_id) if uses_v02_timeline else set()
    dynasty_ids = get_preset_dynasty_ids(preset_id) if uses_v02_timeline else set()
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
        dynasty_id = event.get("dynasty_id")
        if uses_v02_timeline and dynasty_id is not None and str(dynasty_id) not in dynasty_ids:
            raise MissingReferenceError(f"{path}.dynasty_id", dynasty_id, "preset dynasties.json")
        trigger = _require(event, "trigger", path)
        if not isinstance(trigger, dict):
            raise ScenarioValidationError(f"{path}.trigger", "object", trigger)
        for key in ("year", "month"):
            value = _require(trigger, key, f"{path}.trigger")
            if not isinstance(value, int):
                raise ScenarioValidationError(f"{path}.trigger.{key}", "integer", value)
        at_region_id = trigger.get("at_region_id")
        if uses_v02_timeline and at_region_id is not None and str(at_region_id) not in region_ids:
            raise MissingReferenceError(f"{path}.trigger.at_region_id", at_region_id, "preset regions.json")

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
    _validate_generation_sources(scenario, preset_id=preset_id)
    _warn_if_random_sect_count_exceeds_pool(scenario, preset_id=preset_id)
    _validate_initial_state(scenario, preset_id)
    timeline = _validate_timeline(timeline_data, preset_id=preset_id, scenario_schema_version=str(scenario["schema_version"]))
    return ResolvedScenario(
        scenario_id=str(scenario["scenario_id"]),
        title=str(scenario["title"]),
        version=str(scenario["version"]),
        preset_id=preset_id,
        scenario=scenario,
        timeline=timeline,
        scenario_dir=scenario_dir,
    )


def validate_scenario_dir(scenario_dir: Path) -> ScenarioDirectoryValidationResult:
    scenario_path = scenario_dir / "scenario.json"
    timeline_path = scenario_dir / "timeline.json"
    scenario = _load_json(scenario_path, required=True)
    timeline_data = _load_json(timeline_path, required=True)

    preset_id = _validate_scenario_top_level(scenario)
    if str(scenario["scenario_id"]) != scenario_dir.name:
        raise ScenarioValidationError(
            "scenario.scenario_id",
            f"matching package directory name {scenario_dir.name!r}",
            scenario["scenario_id"],
        )

    _validate_generation_sources(scenario, preset_id=preset_id)
    _warn_if_random_sect_count_exceeds_pool(scenario, preset_id=preset_id)
    _validate_initial_state(scenario, preset_id)
    _validate_timeline(
        timeline_data,
        preset_id=preset_id,
        scenario_schema_version=str(scenario["schema_version"]),
    )

    warnings: list[str] = []
    known_keys = {
        "schema_version",
        "scenario_id",
        "title",
        "version",
        "description",
        "author",
        "tags",
        "cover_image",
        "dependencies",
        "engine",
        "fingerprint",
        "world_preset",
        "generation_sources",
        "initial_state",
    }
    unknown_keys = sorted(str(key) for key in scenario if key not in known_keys)
    if unknown_keys:
        warnings.append(f"Unknown scenario.json fields ignored: {', '.join(unknown_keys)}")
    for key in ("tags", "cover_image", "author"):
        if key not in scenario:
            warnings.append(f"Optional metadata missing: {key}")

    return ScenarioDirectoryValidationResult(
        scenario_id=str(scenario["scenario_id"]),
        title=str(scenario["title"]),
        version=str(scenario["version"]),
        preset_id=preset_id,
        warnings=warnings,
    )
