from __future__ import annotations

import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.config.presets import load_preset_json, set_active_preset
from src.scenario.scenario_loader import load
from src.scenario.source_resolver import clear_active_scenario_source, set_active_scenario_source
from src.server.init_flow import _select_scenario_existed_sects, resolve_generation_counts


class _Sect:
    def __init__(self, sect_id: int):
        self.id = sect_id


def _settings(init_npc_num: int = 0, sect_num: int = 0):
    return SimpleNamespace(init_npc_num=init_npc_num, sect_num=sect_num)


@pytest.fixture(autouse=True)
def reset_source_context():
    set_active_preset("default")
    clear_active_scenario_source()
    yield
    clear_active_scenario_source()
    set_active_preset("default")


def _scenario_sect_count(scenario_id: str, *, random_sect_count: int) -> int:
    resolved = load(scenario_id)
    resolved.scenario["initial_state"]["generation_profile"]["random_sect_count"] = random_sect_count
    set_active_scenario_source(resolved)
    counts = resolve_generation_counts(scenario=resolved, settings=_settings(sect_num=0))
    sect_ids = load_preset_json(resolved.preset_id, "sects.json")["sect_ids"]
    selected = _select_scenario_existed_sects(
        sects_by_id={int(sect_id): _Sect(int(sect_id)) for sect_id in sect_ids},
        random_sect_count=counts["sect_count"],
        resolved_scenario=resolved,
    )
    return len(selected)


def _scenario_data(*, scenario_id: str, preset_id: str, random_sect_count: int | None, sects: list[dict]) -> dict:
    initial_state = {
        "year": 1,
        "month": 1,
        "avatars": [],
        "sects": sects,
        "relationships": [],
        "world_flags": {},
    }
    if random_sect_count is not None:
        initial_state["generation_profile"] = {"random_sect_count": random_sect_count}
    return {
        "schema_version": "1.2",
        "scenario_id": scenario_id,
        "title": "Pool Warning Fixture",
        "version": "1.0",
        "world_preset": {"preset_id": preset_id},
        "generation_sources": {"sects": "scenario", "fallback_to_default": False},
        "initial_state": initial_state,
    }


def _write_scenario(root: Path, scenario: dict) -> Path:
    scenario_dir = root / str(scenario["scenario_id"])
    scenario_dir.mkdir(parents=True)
    (scenario_dir / "scenario.json").write_text(json.dumps(scenario, ensure_ascii=False), encoding="utf-8")
    (scenario_dir / "timeline.json").write_text(
        json.dumps({"schema_version": "0.1", "events": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    return root


def _sect_pool_warning_messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == "src.scenario.scenario_loader"
        and record.levelno == logging.WARNING
        and "random_sect_count" in record.getMessage()
    ]


def test_liuchao_random_sect_count_now_reaches_target_or_pool_cap():
    assert _scenario_sect_count("liuchao", random_sect_count=10) >= 8


def test_sanguo_random_sect_count_reaches_pool_cap():
    assert _scenario_sect_count("sanguo", random_sect_count=10) >= 8


def test_warning_NOT_emitted_when_random_sect_count_within_pool(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    scenario = _scenario_data(
        scenario_id="pool_within_fixture",
        preset_id="liuchao",
        random_sect_count=5,
        sects=[{"id": 1, "leader_avatar_id": None, "member_avatar_ids": []}],
    )
    root = _write_scenario(tmp_path / "scenarios", scenario)

    with caplog.at_level(logging.WARNING, logger="src.scenario.scenario_loader"):
        load("pool_within_fixture", scenarios_root=root)

    assert _sect_pool_warning_messages(caplog) == []


def test_warning_emitted_when_random_sect_count_exceeds_pool(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    scenario = _scenario_data(
        scenario_id="pool_warning_fixture",
        preset_id="liuchao",
        random_sect_count=99,
        sects=[{"id": 1, "leader_avatar_id": None, "member_avatar_ids": []}],
    )
    root = _write_scenario(tmp_path / "scenarios", scenario)
    pool_size = len(load_preset_json("liuchao", "sects.json")["sects"])
    scripted_count = len(scenario["initial_state"]["sects"])
    available = max(0, pool_size - scripted_count)

    with caplog.at_level(logging.WARNING, logger="src.scenario.scenario_loader"):
        load("pool_warning_fixture", scenarios_root=root)

    messages = _sect_pool_warning_messages(caplog)
    assert len(messages) == 1
    message = messages[0]
    assert "pool_warning_fixture" in message
    assert "random_sect_count=99" in message
    assert f"available_count={available}" in message
    assert f"scripted_count={scripted_count}" in message
    assert f"effective_cap={available}" in message


def test_warning_NOT_emitted_when_no_scenario(caplog: pytest.LogCaptureFixture):
    clear_active_scenario_source()

    with caplog.at_level(logging.WARNING, logger="src.scenario.scenario_loader"):
        counts = resolve_generation_counts(scenario=None, settings=_settings(sect_num=99))

    assert counts["sect_count"] == 99
    assert _sect_pool_warning_messages(caplog) == []
