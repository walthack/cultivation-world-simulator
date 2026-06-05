from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.config.data_paths import get_data_paths
from src.scenario.scenario_loader import validate_scenario_dir
from src.server.api.public_v1.command import create_public_command_router
from src.server.api.public_v1.query import create_public_query_router
from src.server.services.scenario_generate import generate_scenario_from_description
from src.server.services.scenario_templates import list_templates, load_template


def _valid_draft(scenario_id: str = "authoring_valid") -> dict:
    return {
        "scenario": {
            "schema_version": "0.1",
            "scenario_id": scenario_id,
            "title": "Authoring Valid",
            "version": "1.0",
            "author": "Test",
            "description": "Valid authoring draft.",
            "tags": ["test"],
            "world_preset": {"preset_id": "default"},
            "initial_state": {
                "year": 1,
                "month": 1,
                "avatars": [],
                "relationships": [],
                "sects": [],
                "world_flags": {},
            },
        },
        "timeline": {"schema_version": "0.1", "events": []},
    }


def _command_client() -> TestClient:
    async def async_noop(*_args, **_kwargs):
        return {}

    def noop(*_args, **_kwargs):
        return {}

    app = FastAPI()
    app.include_router(
        create_public_command_router(
            run_start_game=async_noop,
            run_reinit_game=async_noop,
            run_reset_game=async_noop,
            trigger_process_shutdown=noop,
            run_pause_game=async_noop,
            run_resume_game=async_noop,
            run_set_long_term_objective=async_noop,
            run_clear_long_term_objective=async_noop,
            run_create_avatar=async_noop,
            run_delete_avatar=async_noop,
            run_update_avatar_adjustment=async_noop,
            run_update_avatar_portrait=async_noop,
            run_generate_custom_content=async_noop,
            run_create_custom_content=noop,
            run_set_phenomenon=async_noop,
            run_bulk_import_world=async_noop,
            run_cleanup_events=async_noop,
            run_save_game=noop,
            run_delete_save=noop,
            run_load_game=async_noop,
            run_start_roleplay=async_noop,
            run_stop_roleplay=async_noop,
            run_submit_roleplay_decision=async_noop,
            run_submit_roleplay_choice=async_noop,
            run_send_roleplay_conversation=async_noop,
            run_end_roleplay_conversation=async_noop,
        )
    )
    return TestClient(app)


def _query_client() -> TestClient:
    def empty():
        return {}

    app = FastAPI()
    app.include_router(
        create_public_query_router(
            build_runtime_status=empty,
            build_world_state=empty,
            build_world_map=empty,
            build_current_run=empty,
            build_events_page=lambda **_kwargs: {},
            build_rankings=empty,
            build_sect_relations=empty,
            build_game_data=empty,
            build_avatar_adjust_options=empty,
            build_avatar_meta=empty,
            build_avatar_list=empty,
            build_phenomena=empty,
            build_sect_territories=empty,
            build_mortal_overview=empty,
            build_dynasty_overview=empty,
            build_dynasty_detail=empty,
            build_scenario_status=empty,
            build_installed_scenarios=lambda: {"scenarios": []},
            build_avatar_overview=empty,
            build_saves=empty,
            build_detail=lambda **_kwargs: {},
            build_deceased_list=empty,
            build_roleplay_session=empty,
        )
    )
    return TestClient(app)


def test_list_templates_returns_three_categories():
    response = _query_client().get("/api/v1/query/scenario/templates")

    assert response.status_code == 200
    categories = {item["category"] for item in response.json()["data"]["templates"]}
    assert categories == {"historical", "fantasy", "sandbox"}
    assert {template.category for template in list_templates()} == categories


def test_each_template_loads_as_valid_scenario_draft():
    for category in ("historical", "fantasy", "sandbox"):
        draft = load_template(category)
        scenario = draft["scenario"]
        timeline = draft["timeline"]
        with tempfile.TemporaryDirectory() as tmp_name:
            scenario_dir = Path(tmp_name) / scenario["scenario_id"]
            scenario_dir.mkdir()
            (scenario_dir / "scenario.json").write_text(json.dumps(scenario), encoding="utf-8")
            (scenario_dir / "timeline.json").write_text(json.dumps(timeline), encoding="utf-8")
            validation = validate_scenario_dir(scenario_dir)
        assert validation.scenario_id == scenario["scenario_id"]


@pytest.mark.asyncio
async def test_generate_scenario_from_description_with_valid_llm_mock_returns_parsed_draft(monkeypatch):
    async def fake_call_llm_json(*_args, **_kwargs):
        return _valid_draft("generated_valid")

    monkeypatch.setattr("src.server.services.scenario_generate.call_llm_json", fake_call_llm_json)

    result = await generate_scenario_from_description("make a valid world", {"preset_id": "default"})

    assert result.ok is True
    assert result.draft["scenario"]["scenario_id"] == "generated_valid"
    assert result.attempts == 1


@pytest.mark.asyncio
async def test_generate_invalid_llm_output_retries_once(monkeypatch):
    calls = []

    async def fake_call_llm_json(*_args, **_kwargs):
        calls.append(1)
        if len(calls) == 1:
            return {"scenario": {"scenario_id": "broken"}}
        return _valid_draft("generated_after_retry")

    monkeypatch.setattr("src.server.services.scenario_generate.call_llm_json", fake_call_llm_json)

    result = await generate_scenario_from_description("retry this", {"preset_id": "default"})

    assert result.ok is True
    assert result.draft["scenario"]["scenario_id"] == "generated_after_retry"
    assert result.attempts == 2
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_generate_persistent_invalid_returns_raw_and_errors(monkeypatch):
    async def fake_call_llm_json(*_args, **_kwargs):
        return {"scenario": {"scenario_id": "still_broken"}}

    monkeypatch.setattr("src.server.services.scenario_generate.call_llm_json", fake_call_llm_json)

    result = await generate_scenario_from_description("still invalid", {"preset_id": "default"})

    assert result.ok is False
    assert result.raw_output == {"scenario": {"scenario_id": "still_broken"}}
    assert result.validation_errors
    assert result.attempts == 2


def test_save_draft_endpoint_persists_to_data_root_scenarios():
    client = _command_client()
    draft = _valid_draft("saved_authoring")

    response = client.post("/api/v1/command/scenario/save-draft", json=draft)

    assert response.status_code == 200
    data = response.json()["data"]
    saved_dir = get_data_paths().root / "scenarios" / "saved_authoring"
    assert data["scenario_id"] == "saved_authoring"
    assert data["zip_base64"]
    assert (saved_dir / "scenario.json").is_file()
    assert (saved_dir / "timeline.json").is_file()
