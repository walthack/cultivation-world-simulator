from __future__ import annotations

import json
from pathlib import Path

import pytest

import src.config.presets as presets
from src.config.presets import PresetConfigError, get_preset_orthodoxies
from src.scenario.scenario_loader import load


def test_default_orthodoxy_axes_are_numeric():
    orthodoxies = get_preset_orthodoxies("default")

    assert {item["id"] for item in orthodoxies} >= {"dao", "buddhism", "confucianism", "sanxiu", "wu"}
    for orthodoxy in orthodoxies:
        assert isinstance(orthodoxy.get("axes"), dict)
        assert all(isinstance(value, (int, float)) for value in orthodoxy["axes"].values())


def test_liuchao_orthodoxy_contains_multi_axis_positions():
    taiyi = next(item for item in get_preset_orthodoxies("liuchao") if item["id"] == "taiyi_dao")

    assert taiyi["axes"]["修行"] == 100
    assert taiyi["axes"]["隐秘"] == 45


def test_orthodoxy_rejects_non_numeric_axis(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    preset = tmp_path / "presets" / "bad"
    preset.mkdir(parents=True)
    (preset / "orthodoxies.json").write_text(
        json.dumps(
            {
                "preset_id": "bad",
                "orthodoxies": [
                    {"id": "bad-axis", "name": "Bad", "description": "", "axes": {"汉统": "high"}, "tags": []}
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(presets, "get_presets_root", lambda: tmp_path / "presets")

    with pytest.raises(PresetConfigError, match="axis value must be numeric"):
        get_preset_orthodoxies("bad")


def test_v01_scenario_still_loads_after_orthodoxy_schema():
    scenario = load("sample")

    assert scenario.scenario_id == "sample"
