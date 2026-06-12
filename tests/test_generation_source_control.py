from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.classes.items.weapon import get_random_weapon_by_realm
from src.classes.persona import get_random_compatible_personas
from src.config.presets import set_active_preset
from src.run.data_loader import reload_all_static_data
from src.scenario import scenario_loader, source_resolver
from src.scenario.scenario_loader import ScenarioValidationError, load
from src.scenario.source_resolver import (
    clear_active_scenario_source,
    resolve_source,
    set_active_scenario_source,
)
from src.systems.cultivation import Realm


@pytest.fixture(autouse=True)
def reset_source_context():
    set_active_preset("default")
    clear_active_scenario_source()
    reload_all_static_data()
    yield
    clear_active_scenario_source()


def _scenario_data(*, generation_sources: dict | None = None, preset_id: str = "default") -> dict:
    data = {
        "schema_version": "1.2",
        "scenario_id": "source_fixture",
        "title": "Source Fixture",
        "version": "1.0",
        "world_preset": {"preset_id": preset_id},
        "initial_state": {
            "year": 1,
            "month": 1,
            "avatars": [],
            "sects": [],
            "relationships": [],
            "world_flags": {},
        },
    }
    if generation_sources is not None:
        data["generation_sources"] = generation_sources
    return data


def _write_scenario(root: Path, scenario: dict) -> Path:
    scenario_dir = root / "source_fixture"
    scenario_dir.mkdir(parents=True)
    (scenario_dir / "scenario.json").write_text(json.dumps(scenario, ensure_ascii=False), encoding="utf-8")
    (scenario_dir / "timeline.json").write_text(
        json.dumps({"schema_version": "0.1", "events": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    return root


def _minimal_preset(root: Path, preset_id: str, *, include_weapons: bool = True) -> None:
    preset_dir = root / preset_id
    preset_dir.mkdir(parents=True)
    (preset_dir / "sects.json").write_text(json.dumps({"preset_id": preset_id, "sect_ids": []}), encoding="utf-8")
    (preset_dir / "realms.json").write_text(
        json.dumps(
            {
                "preset_id": preset_id,
                "realm_order": ["QI_REFINEMENT"],
                "stage_order": ["EARLY_STAGE"],
            }
        ),
        encoding="utf-8",
    )
    (preset_dir / "personas.json").write_text(
        json.dumps({"preset_id": preset_id, "persona_keys": ["RATIONAL"]}),
        encoding="utf-8",
    )
    (preset_dir / "goldfingers.json").write_text(
        json.dumps({"preset_id": preset_id, "goldfinger_keys": ["CHILD_OF_FORTUNE"]}),
        encoding="utf-8",
    )
    if include_weapons:
        (preset_dir / "weapons.json").write_text(
            json.dumps(
                {
                    "preset_id": preset_id,
                    "weapons": [
                        {
                            "id": "fixture-weapon",
                            "name": "Fixture Sword",
                            "tier": 1,
                            "attributes": ["SWORD"],
                            "effects": [],
                            "required_realm": "QI_REFINEMENT",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )


def _patch_preset_root(monkeypatch: pytest.MonkeyPatch, presets_root: Path) -> None:
    import src.config.presets as presets

    monkeypatch.setattr(presets, "get_presets_root", lambda: presets_root)
    monkeypatch.setattr(scenario_loader, "get_presets_root", lambda: presets_root)
    monkeypatch.setattr(source_resolver, "get_presets_root", lambda: presets_root)


def test_no_scenario_uses_default_sources():
    clear_active_scenario_source()

    for kind in ("npc_names", "personas", "weapons", "techniques"):
        handle = resolve_source(kind)
        assert handle.preset_id == "default"
        assert handle.provenance == "default"


def test_scenario_all_sources_scenario_with_fallback_false_loads_clean():
    resolved = load("liuchao")

    assert resolved.scenario_id == "liuchao"
    assert resolved.scenario["schema_version"] == "1.2"
    assert resolved.scenario["generation_sources"]["fallback_to_default"] is False


def test_scenario_source_scenario_hits_preset_pool():
    resolved = load("liuchao")
    set_active_scenario_source(resolved)
    reload_all_static_data()

    expected_names = {
        "现代知识", "商业谈判", "临机权变", "忠义守诺", "军伍果断",
        "医者仁心", "情报谋算", "巫毒秘术", "朝堂权术", "江湖侠义",
    }
    picked = {persona.name for _ in range(8) for persona in get_random_compatible_personas(1)}

    assert picked
    assert picked <= expected_names
    assert resolve_source("personas").provenance == "scenario:liuchao"


def test_scenario_source_default_overrides_to_default_pool():
    scenario = SimpleNamespace(
        scenario_id="override_fixture",
        preset_id="liuchao",
        scenario={
            "schema_version": "1.2",
            "scenario_id": "override_fixture",
            "world_preset": {"preset_id": "liuchao"},
            "generation_sources": {"personas": "default", "fallback_to_default": False},
        },
    )
    set_active_scenario_source(scenario)
    reload_all_static_data()

    liuchao_names = {
        "现代知识", "商业谈判", "临机权变", "忠义守诺", "军伍果断",
        "医者仁心", "情报谋算", "巫毒秘术", "朝堂权术", "江湖侠义",
    }
    picked = {persona.name for _ in range(8) for persona in get_random_compatible_personas(1)}

    assert picked
    assert picked.isdisjoint(liuchao_names)
    assert resolve_source("personas").preset_id == "default"


def test_fallback_to_default_true_silently_uses_default_when_preset_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    presets_root = tmp_path / "presets"
    _minimal_preset(presets_root, "default", include_weapons=True)
    _minimal_preset(presets_root, "missing_weapon", include_weapons=False)
    _patch_preset_root(monkeypatch, presets_root)

    root = _write_scenario(
        tmp_path / "scenarios",
        _scenario_data(
            preset_id="missing_weapon",
            generation_sources={"weapons": "scenario", "fallback_to_default": True},
        ),
    )

    resolved = load("source_fixture", scenarios_root=root)
    set_active_scenario_source(resolved)

    handle = resolve_source("weapons")
    assert handle.preset_id == "default"
    assert handle.provenance == "default:fallback-missing-missing_weapon:weapons"
    assert get_random_weapon_by_realm(Realm.Qi_Refinement).name == "Fixture Sword"


def test_generation_sources_omitted_preserves_v1_1_behavior():
    scenario = SimpleNamespace(
        scenario_id="v11_fixture",
        preset_id="liuchao",
        scenario={
            "schema_version": "1.1",
            "scenario_id": "v11_fixture",
            "world_preset": {"preset_id": "liuchao"},
        },
    )
    set_active_scenario_source(scenario)

    handle = resolve_source("personas")
    assert handle.preset_id == "default"
    assert handle.provenance == "default:v1.1-implicit"


def test_loader_rejects_invalid_source_value(tmp_path: Path):
    root = _write_scenario(
        tmp_path / "scenarios",
        _scenario_data(generation_sources={"sects": "wrong_string", "fallback_to_default": False}),
    )

    with pytest.raises(ScenarioValidationError, match="generation_sources.sects"):
        load("source_fixture", scenarios_root=root)


def test_loader_rejects_non_bool_fallback_to_default(tmp_path: Path):
    root = _write_scenario(
        tmp_path / "scenarios",
        _scenario_data(generation_sources={"sects": "scenario", "fallback_to_default": "yes"}),
    )

    with pytest.raises(ScenarioValidationError, match="fallback_to_default"):
        load("source_fixture", scenarios_root=root)


def test_loader_raises_when_preset_missing_and_fallback_false(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    presets_root = tmp_path / "presets"
    _minimal_preset(presets_root, "missing_weapon", include_weapons=False)
    _patch_preset_root(monkeypatch, presets_root)
    root = _write_scenario(
        tmp_path / "scenarios",
        _scenario_data(
            preset_id="missing_weapon",
            generation_sources={"weapons": "scenario", "fallback_to_default": False},
        ),
    )

    expected_path = presets_root / "missing_weapon" / "weapons.json"
    with pytest.raises(ScenarioValidationError) as exc_info:
        load("source_fixture", scenarios_root=root)

    message = str(exc_info.value)
    assert "source_fixture" in message
    assert "weapons" in message
    assert str(expected_path) in message
