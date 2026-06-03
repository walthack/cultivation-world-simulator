from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.server.api.public_v1.query import create_public_query_router
from src.server.services.scenario_registry import list_installed_scenarios


def _client_for_installed_scenarios(builder):
    app = FastAPI()
    noop = lambda: {}
    app.include_router(
        create_public_query_router(
            build_runtime_status=noop,
            build_world_state=noop,
            build_world_map=noop,
            build_current_run=noop,
            build_events_page=lambda **_kwargs: {},
            build_rankings=noop,
            build_sect_relations=noop,
            build_game_data=noop,
            build_avatar_adjust_options=noop,
            build_avatar_meta=noop,
            build_avatar_list=noop,
            build_phenomena=noop,
            build_sect_territories=noop,
            build_mortal_overview=noop,
            build_dynasty_overview=noop,
            build_dynasty_detail=noop,
            build_scenario_status=noop,
            build_installed_scenarios=builder,
            build_avatar_overview=noop,
            build_saves=noop,
            build_detail=lambda **_kwargs: {},
            build_deceased_list=noop,
            build_roleplay_session=noop,
        )
    )
    return TestClient(app)


def test_list_installed_scenarios_returns_bundled_liuchao_and_sanguo():
    scenarios = list_installed_scenarios()
    by_id = {scenario.id: scenario for scenario in scenarios}

    assert {"liuchao", "sanguo"}.issubset(by_id)
    assert by_id["liuchao"].name == "六朝纪事"
    assert by_id["sanguo"].name == "三国仙纪"


def test_list_installed_scenarios_skips_invalid_scenario_json(tmp_path):
    valid_dir = tmp_path / "valid"
    valid_dir.mkdir()
    (valid_dir / "scenario.json").write_text(
        json.dumps(
            {
                "scenario_id": "valid",
                "title": "Valid Scenario",
                "version": "1.0",
                "description": "Valid metadata",
            }
        ),
        encoding="utf-8",
    )
    invalid_dir = tmp_path / "invalid"
    invalid_dir.mkdir()
    (invalid_dir / "scenario.json").write_text("{", encoding="utf-8")

    scenarios = list_installed_scenarios(scenarios_root=tmp_path)

    assert [scenario.id for scenario in scenarios] == ["valid"]


def test_get_installed_scenarios_api_maps_title_to_name():
    client = _client_for_installed_scenarios(
        lambda: {
            "scenarios": [
                scenario.model_dump()
                for scenario in list_installed_scenarios()
                if scenario.id in {"liuchao", "sanguo"}
            ]
        }
    )

    response = client.get("/api/v1/query/scenarios")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    scenarios = {scenario["id"]: scenario for scenario in body["data"]["scenarios"]}
    assert scenarios["liuchao"]["name"] == "六朝纪事"
    assert scenarios["sanguo"]["name"] == "三国仙纪"
    assert scenarios["liuchao"]["tags"] == []
    assert scenarios["liuchao"]["cover_image"] is None
