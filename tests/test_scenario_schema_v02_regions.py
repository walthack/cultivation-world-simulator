from __future__ import annotations

import json
from pathlib import Path

import pytest

import src.config.presets as presets
from src.config.presets import PresetConfigError, get_preset_regions
from src.scenario.scenario_loader import MissingReferenceError, load


def _scenario(
    tmp_path: Path,
    *,
    schema_version: str = "0.2",
    avatar_patch: dict | None = None,
    sect_patch: dict | None = None,
    trigger_patch: dict | None = None,
) -> Path:
    root = tmp_path / "scenarios"
    scenario_dir = root / "region_fixture"
    scenario_dir.mkdir(parents=True)
    avatar = {
        "id": "avatar-1",
        "surname": "地",
        "given_name": "域",
        "gender": "男",
        "age": 30,
        "sect_id": 1,
        "realm": "QI_REFINEMENT",
        "stage": "EARLY_STAGE",
        "level": 1,
        "persona_traits": ["RATIONAL"],
        "goldfinger_id": "CHILD_OF_FORTUNE",
    }
    if avatar_patch:
        avatar.update(avatar_patch)
    sect = {"id": 1, "leader_avatar_id": "avatar-1", "member_avatar_ids": ["avatar-1"]}
    if sect_patch:
        sect.update(sect_patch)
    trigger = {"year": 1, "month": 1}
    if trigger_patch:
        trigger.update(trigger_patch)
    payload = {
        "schema_version": schema_version,
        "scenario_id": "region_fixture",
        "title": "Region Fixture",
        "version": "1.0",
        "world_preset": {"preset_id": "default"},
        "initial_state": {
            "year": 1,
            "month": 1,
            "avatars": [avatar],
            "sects": [sect],
            "relationships": [],
            "world_flags": {},
        },
    }
    timeline = {
        "schema_version": schema_version,
        "events": [
            {
                "id": "region-event",
                "type": "world_event",
                "trigger": trigger,
                "name": "Region Event",
                "description": "Region fixture.",
                "effects": [],
            }
        ],
    }
    (scenario_dir / "scenario.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    (scenario_dir / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False), encoding="utf-8")
    return root


def test_default_regions_include_three_region_types():
    types = {item["type"] for item in get_preset_regions("default")}

    assert types == {"city", "cultivate", "normal"}


def test_v02_avatar_location_region_ref_passes(tmp_path: Path):
    root = _scenario(tmp_path, avatar_patch={"location_region_id": "301"})

    scenario = load("region_fixture", scenarios_root=root)

    assert scenario.scenario["initial_state"]["avatars"][0]["location_region_id"] == "301"


def test_v02_avatar_location_region_unknown_raises(tmp_path: Path):
    root = _scenario(tmp_path, avatar_patch={"location_region_id": "missing-region"})

    with pytest.raises(MissingReferenceError, match="location_region_id"):
        load("region_fixture", scenarios_root=root)


def test_v02_sect_headquarters_region_ref_passes(tmp_path: Path):
    root = _scenario(tmp_path, sect_patch={"headquarters_region_id": "301"})

    scenario = load("region_fixture", scenarios_root=root)

    assert scenario.scenario["initial_state"]["sects"][0]["headquarters_region_id"] == "301"


def test_v02_sect_headquarters_region_unknown_raises(tmp_path: Path):
    root = _scenario(tmp_path, sect_patch={"headquarters_region_id": "missing-region"})

    with pytest.raises(MissingReferenceError, match="headquarters_region_id"):
        load("region_fixture", scenarios_root=root)


def test_v02_timeline_trigger_region_ref_passes(tmp_path: Path):
    root = _scenario(tmp_path, trigger_patch={"at_region_id": "301"})

    scenario = load("region_fixture", scenarios_root=root)

    assert scenario.timeline[0]["trigger"]["at_region_id"] == "301"


def test_v02_timeline_trigger_region_unknown_raises(tmp_path: Path):
    root = _scenario(tmp_path, trigger_patch={"at_region_id": "missing-region"})

    with pytest.raises(MissingReferenceError, match="at_region_id"):
        load("region_fixture", scenarios_root=root)


def test_region_rejects_unknown_dynasty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    preset = tmp_path / "presets" / "bad"
    preset.mkdir(parents=True)
    (preset / "dynasties.json").write_text(
        json.dumps({"preset_id": "bad", "dynasties": []}),
        encoding="utf-8",
    )
    (preset / "regions.json").write_text(
        json.dumps(
            {
                "preset_id": "bad",
                "regions": [
                    {
                        "id": "bad-region",
                        "name": "Bad",
                        "type": "city",
                        "description": "",
                        "dynasty_id": "missing",
                        "climate": "",
                        "economic_focus": "",
                        "key_landmarks": [],
                        "tags": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(presets, "get_presets_root", lambda: tmp_path / "presets")

    with pytest.raises(PresetConfigError, match="unknown dynasty_id"):
        get_preset_regions("bad")


def test_v01_scenario_without_region_fields_still_loads(tmp_path: Path):
    root = _scenario(tmp_path, schema_version="0.1")

    assert load("region_fixture", scenarios_root=root).scenario_id == "region_fixture"
