from __future__ import annotations

import json
from pathlib import Path

import pytest

import src.scenario.scenario_loader as scenario_loader
from src.scenario.scenario_loader import MissingReferenceError, ScenarioValidationError, load


def _scenario(tmp_path: Path, *, schema_version: str = "0.2", dynasties: list[dict] | None = None) -> Path:
    root = tmp_path / "scenarios"
    scenario_dir = root / "dynasty_fixture"
    scenario_dir.mkdir(parents=True)
    payload = {
        "schema_version": schema_version,
        "scenario_id": "dynasty_fixture",
        "title": "Dynasty Fixture",
        "version": "1.0",
        "world_preset": {"preset_id": "default"},
        "initial_state": {
            "year": 1,
            "month": 1,
            "avatars": [
                {
                    "id": "ruler-1",
                    "surname": "君",
                    "given_name": "一",
                    "gender": "男",
                    "age": 40,
                    "sect_id": None,
                    "realm": "QI_REFINEMENT",
                    "stage": "EARLY_STAGE",
                    "level": 1,
                    "persona_traits": ["RATIONAL"],
                    "goldfinger_id": "CHILD_OF_FORTUNE",
                }
            ],
            "sects": [],
            "relationships": [],
            "world_flags": {},
        },
    }
    if dynasties is not None:
        payload["initial_state"]["dynasties"] = dynasties
    (scenario_dir / "scenario.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return root


def _valid_dynasty(**patch) -> dict:
    dynasty = {
        "id": "test-dynasty",
        "name": "测试朝",
        "description": "Dynasty fixture.",
        "capital_region_id": "capital",
        "ruler_avatar_id": "ruler-1",
        "territory_region_ids": ["capital", "border"],
        "status": "active",
        "founding_year": 1,
        "relations": [
            {"other_dynasty_id": "other-dynasty", "type": "ally", "value": 50},
        ],
        "orthodoxy_ids": ["dao"],
    }
    dynasty.update(patch)
    return dynasty


def _patch_reference_sets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scenario_loader, "get_preset_dynasty_ids", lambda preset_id: {"other-dynasty"})
    monkeypatch.setattr(scenario_loader, "get_preset_region_ids", lambda preset_id: {"capital", "border"})
    monkeypatch.setattr(scenario_loader, "get_preset_orthodoxy_ids", lambda preset_id: {"dao"})


def test_v02_dynasty_valid_refs_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _patch_reference_sets(monkeypatch)
    root = _scenario(tmp_path, dynasties=[_valid_dynasty()])

    scenario = load("dynasty_fixture", scenarios_root=root)

    assert scenario.scenario["initial_state"]["dynasties"][0]["id"] == "test-dynasty"


def test_v02_dynasty_unknown_capital_region_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _patch_reference_sets(monkeypatch)
    root = _scenario(tmp_path, dynasties=[_valid_dynasty(capital_region_id="missing")])

    with pytest.raises(MissingReferenceError, match="capital_region_id"):
        load("dynasty_fixture", scenarios_root=root)


def test_v02_dynasty_unknown_territory_region_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _patch_reference_sets(monkeypatch)
    root = _scenario(tmp_path, dynasties=[_valid_dynasty(territory_region_ids=["capital", "missing"])])

    with pytest.raises(MissingReferenceError, match="territory_region_ids"):
        load("dynasty_fixture", scenarios_root=root)


def test_v02_dynasty_unknown_orthodoxy_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _patch_reference_sets(monkeypatch)
    root = _scenario(tmp_path, dynasties=[_valid_dynasty(orthodoxy_ids=["missing"])])

    with pytest.raises(MissingReferenceError, match="orthodoxy_ids"):
        load("dynasty_fixture", scenarios_root=root)


def test_v02_dynasty_unknown_ruler_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _patch_reference_sets(monkeypatch)
    root = _scenario(tmp_path, dynasties=[_valid_dynasty(ruler_avatar_id="missing-avatar")])

    with pytest.raises(MissingReferenceError, match="ruler_avatar_id"):
        load("dynasty_fixture", scenarios_root=root)


def test_v02_dynasty_relation_value_range_validation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _patch_reference_sets(monkeypatch)
    bad = _valid_dynasty(relations=[{"other_dynasty_id": "other-dynasty", "type": "ally", "value": 101}])
    root = _scenario(tmp_path, dynasties=[bad])

    with pytest.raises(ScenarioValidationError, match="relations"):
        load("dynasty_fixture", scenarios_root=root)


def test_v01_without_dynasties_loads(tmp_path: Path):
    root = _scenario(tmp_path, schema_version="0.1")

    assert load("dynasty_fixture", scenarios_root=root).scenario_id == "dynasty_fixture"
