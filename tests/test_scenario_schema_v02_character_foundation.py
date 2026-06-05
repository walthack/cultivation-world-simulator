from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.scenario.scenario_loader import MissingReferenceError, ScenarioValidationError, load


def _scenario(tmp_path: Path, *, schema_version: str = "0.2", avatar_patch: dict | None = None) -> Path:
    root = tmp_path / "scenarios"
    scenario_dir = root / "schema_v02"
    scenario_dir.mkdir(parents=True)
    avatar = {
        "id": "sample-avatar",
        "surname": "测",
        "given_name": "试",
        "gender": "男",
        "age": 28,
        "sect_id": None,
        "realm": "QI_REFINEMENT",
        "stage": "EARLY_STAGE",
        "level": 1,
        "persona_traits": ["RATIONAL"],
        "goldfinger_id": "CHILD_OF_FORTUNE",
        "long_term_objective": "Validate schema v0.2.",
    }
    if avatar_patch:
        avatar.update(avatar_patch)
    payload = {
        "schema_version": schema_version,
        "scenario_id": "schema_v02",
        "title": "Schema v0.2",
        "version": "1.0",
        "world_preset": {"preset_id": "default"},
        "initial_state": {
            "year": 1,
            "month": 1,
            "avatars": [avatar],
            "sects": [],
            "relationships": [],
            "world_flags": {},
        },
    }
    (scenario_dir / "scenario.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return root


def test_v02_valid_race_id_passes(tmp_path: Path):
    root = _scenario(tmp_path, avatar_patch={"race_id": "human"})

    scenario = load("schema_v02", scenarios_root=root)

    assert scenario.scenario["initial_state"]["avatars"][0]["race_id"] == "human"


def test_v02_unknown_race_id_raises(tmp_path: Path):
    root = _scenario(tmp_path, avatar_patch={"race_id": "unknown-race"})

    with pytest.raises(MissingReferenceError, match="race_id"):
        load("schema_v02", scenarios_root=root)


def test_v01_without_race_id_loads(tmp_path: Path):
    root = _scenario(tmp_path, schema_version="0.1")

    assert load("schema_v02", scenarios_root=root).scenario_id == "schema_v02"


def test_v02_valid_root_id_passes(tmp_path: Path):
    root = _scenario(tmp_path, avatar_patch={"root_id": "GOLD"})

    scenario = load("schema_v02", scenarios_root=root)

    assert scenario.scenario["initial_state"]["avatars"][0]["root_id"] == "GOLD"


def test_v02_unknown_root_id_raises(tmp_path: Path):
    root = _scenario(tmp_path, avatar_patch={"root_id": "UNKNOWN_ROOT"})

    with pytest.raises(MissingReferenceError, match="root_id"):
        load("schema_v02", scenarios_root=root)


def test_v02_full_persona_dict_passes(tmp_path: Path):
    root = _scenario(
        tmp_path,
        avatar_patch={
            "persona_traits": [
                {
                    "id": "RATIONAL",
                    "name": "理性",
                    "description": "Use logic first.",
                    "stat_modifiers": {"extra_retreat_success_rate": 0.05},
                    "tags": ["N"],
                }
            ]
        },
    )

    scenario = load("schema_v02", scenarios_root=root)

    assert scenario.scenario["initial_state"]["avatars"][0]["persona_traits"][0]["id"] == "RATIONAL"


def test_v02_bare_persona_id_still_passes(tmp_path: Path):
    root = _scenario(tmp_path, avatar_patch={"persona_traits": ["RATIONAL"]})

    assert load("schema_v02", scenarios_root=root).scenario_id == "schema_v02"


def test_v02_unknown_persona_id_raises(tmp_path: Path):
    root = _scenario(tmp_path, avatar_patch={"persona_traits": ["UNKNOWN_PERSONA"]})

    with pytest.raises(MissingReferenceError, match="persona_traits"):
        load("schema_v02", scenarios_root=root)


def test_v02_full_goldfinger_dict_passes(tmp_path: Path):
    root = _scenario(
        tmp_path,
        avatar_patch={
            "goldfinger_id": {
                "id": "CHILD_OF_FORTUNE",
                "side_effects": [],
                "synergies": [],
                "initial_state_patch": {"world_flags": {"blessed": True}},
            }
        },
    )

    scenario = load("schema_v02", scenarios_root=root)

    assert scenario.scenario["initial_state"]["avatars"][0]["goldfinger_id"]["id"] == "CHILD_OF_FORTUNE"


def test_v02_bare_goldfinger_id_still_passes(tmp_path: Path):
    root = _scenario(tmp_path, avatar_patch={"goldfinger_id": "CHILD_OF_FORTUNE"})

    assert load("schema_v02", scenarios_root=root).scenario_id == "schema_v02"


def test_v02_unknown_goldfinger_id_raises(tmp_path: Path):
    root = _scenario(tmp_path, avatar_patch={"goldfinger_id": "UNKNOWN_GOLDFINGER"})

    with pytest.raises(MissingReferenceError, match="goldfinger_id"):
        load("schema_v02", scenarios_root=root)


def test_v02_goldfinger_side_effect_dsl_round_trips(tmp_path: Path):
    side_effect = {"trigger": "monthly_tick", "effect_dsl": "gain_stat:luck:+1"}
    root = _scenario(
        tmp_path,
        avatar_patch={
            "goldfinger_id": {
                "id": "CHILD_OF_FORTUNE",
                "side_effects": [side_effect],
                "synergies": [{"with_goldfinger_id": "TRANSMIGRATOR", "bonus_dsl": "gain_stat:luck:+2"}],
                "initial_state_patch": {},
            }
        },
    )

    scenario = load("schema_v02", scenarios_root=root)

    assert scenario.scenario["initial_state"]["avatars"][0]["goldfinger_id"]["side_effects"] == [side_effect]


def test_v02_invalid_persona_full_model_raises(tmp_path: Path):
    root = _scenario(tmp_path, avatar_patch={"persona_traits": [{"id": "RATIONAL", "tags": "N"}]})

    with pytest.raises(ScenarioValidationError, match="tags"):
        load("schema_v02", scenarios_root=root)
