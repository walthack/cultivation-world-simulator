from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
import shutil

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.config.data_paths import get_data_paths
from src.scenario.scenario_fingerprint import compute_scenario_fingerprint
from src.server.api.public_v1.command import create_public_command_router
from src.server.services.scenario_compat import check_compatibility
from src.server.services.scenario_import import import_scenario_zip
from src.server.services.scenario_repository import (
    archive_root,
    install_from_download,
    list_repository,
    update_from_download,
)


def _scenario_payload(scenario_id: str, version: str = "1.0", *, cws_min: str | None = None) -> dict:
    scenario = {
        "schema_version": "0.1",
        "scenario_id": scenario_id,
        "title": f"{scenario_id} title",
        "version": version,
        "description": f"{scenario_id} description",
        "tags": ["test"],
        "engine": {"schema_version_min": "0.1", "cws_version_min": cws_min or "3.4.0"},
        "dependencies": [],
        "world_preset": {"preset_id": "default"},
        "initial_state": {"avatars": [], "relationships": [], "sects": []},
    }
    return scenario


def _timeline_payload() -> dict:
    return {"schema_version": "0.1", "events": []}


def _write_scenario_dir(root: Path, scenario_id: str, version: str = "1.0", *, fingerprint: bool = False) -> Path:
    scenario_dir = root / scenario_id
    scenario_dir.mkdir(parents=True, exist_ok=True)
    scenario = _scenario_payload(scenario_id, version)
    timeline = _timeline_payload()
    if fingerprint:
        scenario["fingerprint"] = compute_scenario_fingerprint(scenario, timeline)
    (scenario_dir / "scenario.json").write_text(json.dumps(scenario, ensure_ascii=False, indent=2), encoding="utf-8")
    (scenario_dir / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")
    return scenario_dir


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


def test_list_repository_returns_installed_downloaded_and_updates():
    data_root = get_data_paths().root
    _write_scenario_dir(data_root / "scenarios", "repo_case", "1.0")
    _write_scenario_dir(data_root / "scenarios_downloads", "repo_case", "1.1", fingerprint=True)

    repository = list_repository()

    assert [item.id for item in repository.installed] == ["repo_case"]
    assert [item.id for item in repository.downloaded] == ["repo_case"]
    assert len(repository.updates) == 1
    assert repository.downloaded[0].verification.status == "verified"


def test_export_endpoint_returns_valid_zip_readable_by_import():
    data_root = get_data_paths().root
    _write_scenario_dir(data_root / "scenarios", "export_case", "1.0")
    installed_scenario = json.loads((data_root / "scenarios" / "export_case" / "scenario.json").read_text(encoding="utf-8"))

    response = _command_client().post("/api/v1/command/scenario/export", json={"scenario_id": "export_case"})

    assert response.status_code == 200
    assert response.headers["content-disposition"] == 'attachment; filename="export_case.zip"'
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        exported_scenario = json.loads(zf.read("export_case/scenario.json"))
        assert exported_scenario["fingerprint"].startswith("sha256:")
        assert "export_case/scenario_state.json" not in zf.namelist()
    assert "fingerprint" not in installed_scenario
    import_scenario_zip(response.content, rename_to="export_case_roundtrip")
    assert (data_root / "scenarios" / "export_case_roundtrip" / "scenario.json").is_file()


def test_round_trip_export_reimport_yields_verified_repository_status():
    data_root = get_data_paths().root
    _write_scenario_dir(data_root / "scenarios", "verified_case", "1.0")
    exported = _command_client().post("/api/v1/command/scenario/export", json={"scenario_id": "verified_case"}).content
    shutil.rmtree(data_root / "scenarios" / "verified_case")

    import_scenario_zip(exported)

    by_id = {item.id: item for item in list_repository().installed}
    assert by_id["verified_case"].verification.status == "verified"
    assert by_id["verified_case"].verification.claimed is not None


def test_install_from_download_moves_dir_to_installed():
    data_root = get_data_paths().root
    _write_scenario_dir(data_root / "scenarios_downloads", "install_case", "1.0")

    result = install_from_download("install_case")

    assert result["status"] == "installed"
    assert (data_root / "scenarios" / "install_case").is_dir()
    assert not (data_root / "scenarios_downloads" / "install_case").exists()


def test_update_archives_old_version_and_activates_new():
    data_root = get_data_paths().root
    _write_scenario_dir(data_root / "scenarios", "update_case", "1.0")
    _write_scenario_dir(data_root / "scenarios_downloads", "update_case", "1.1")

    result = update_from_download("update_case", "update_case")

    assert result["status"] == "updated"
    assert (archive_root() / "update_case" / "1.0" / "scenario.json").is_file()
    active = json.loads((data_root / "scenarios" / "update_case" / "scenario.json").read_text(encoding="utf-8"))
    assert active["version"] == "1.1"


def test_compatibility_check_fails_when_schema_version_min_exceeds_current():
    scenario = _scenario_payload("compat_fail")
    scenario["engine"]["schema_version_min"] = "9.0"

    result = check_compatibility(scenario, "3.4.0", {"0.1", "0.2"})

    assert result.status == "fail"
    assert result.errors


def test_compatibility_check_warns_on_cws_version_min_mismatch_nonfatal():
    scenario = _scenario_payload("compat_warn")
    scenario["engine"]["cws_version_min"] = "9.0.0"

    result = check_compatibility(scenario, "3.4.0", {"0.1", "0.2"})

    assert result.status == "warn"
    assert result.warnings
