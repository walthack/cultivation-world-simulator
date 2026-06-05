from __future__ import annotations

import json
from pathlib import Path

import pytest

import src.config.presets as presets
from src.config.presets import PresetConfigError, get_preset_techniques, get_preset_weapons
from src.scenario.scenario_loader import MissingReferenceError, load


def _scenario(tmp_path: Path, *, schema_version: str = "0.2", avatar_patch: dict | None = None) -> Path:
    root = tmp_path / "scenarios"
    scenario_dir = root / "schema_v02_content"
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
        "long_term_objective": "Validate content pools.",
    }
    if avatar_patch:
        avatar.update(avatar_patch)
    payload = {
        "schema_version": schema_version,
        "scenario_id": "schema_v02_content",
        "title": "Schema v0.2 Content",
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


def test_v02_valid_technique_ref_passes(tmp_path: Path):
    root = _scenario(tmp_path, avatar_patch={"techniques": [{"technique_id": "1", "level": 2}]})

    scenario = load("schema_v02_content", scenarios_root=root)

    assert scenario.scenario["initial_state"]["avatars"][0]["techniques"][0]["technique_id"] == "1"


def test_v02_unknown_technique_id_raises(tmp_path: Path):
    root = _scenario(tmp_path, avatar_patch={"techniques": [{"technique_id": "unknown", "level": 1}]})

    with pytest.raises(MissingReferenceError, match="technique_id"):
        load("schema_v02_content", scenarios_root=root)


def test_technique_grade_enum_validation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    preset = tmp_path / "presets" / "bad"
    preset.mkdir(parents=True)
    (preset / "techniques.json").write_text(
        json.dumps({"preset_id": "bad", "techniques": [{"id": "x", "name": "Bad", "grade": "immortal"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(presets, "get_presets_root", lambda: tmp_path / "presets")

    with pytest.raises(PresetConfigError, match="invalid grade"):
        get_preset_techniques("bad")


def test_v01_without_techniques_loads(tmp_path: Path):
    root = _scenario(tmp_path, schema_version="0.1")

    assert load("schema_v02_content", scenarios_root=root).scenario_id == "schema_v02_content"


def test_v02_valid_weapon_ref_passes(tmp_path: Path):
    root = _scenario(tmp_path, avatar_patch={"weapons": [{"weapon_id": "1001", "quantity": 1}]})

    scenario = load("schema_v02_content", scenarios_root=root)

    assert scenario.scenario["initial_state"]["avatars"][0]["weapons"][0]["weapon_id"] == "1001"


def test_v02_unknown_weapon_id_raises(tmp_path: Path):
    root = _scenario(tmp_path, avatar_patch={"weapons": [{"weapon_id": "unknown", "quantity": 1}]})

    with pytest.raises(MissingReferenceError, match="weapon_id"):
        load("schema_v02_content", scenarios_root=root)


def test_weapon_tier_range_validation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    preset = tmp_path / "presets" / "bad"
    preset.mkdir(parents=True)
    (preset / "weapons.json").write_text(
        json.dumps({"preset_id": "bad", "weapons": [{"id": "w", "name": "Bad", "tier": 10}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(presets, "get_presets_root", lambda: tmp_path / "presets")

    with pytest.raises(PresetConfigError, match="invalid tier"):
        get_preset_weapons("bad")


def test_v01_without_weapons_loads(tmp_path: Path):
    root = _scenario(tmp_path, schema_version="0.1")

    assert load("schema_v02_content", scenarios_root=root).scenario_id == "schema_v02_content"
