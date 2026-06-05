from __future__ import annotations

import io
import json
import stat
import zipfile
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.config.data_paths import get_data_paths
from src.server.api.public_v1.command import create_public_command_router
from src.server.services.scenario_import import ScenarioImportError, import_scenario_zip
from src.server.services.scenario_registry import list_installed_scenarios


def _scenario_payload(scenario_id: str, *, preset_id: str = "default") -> dict:
    return {
        "schema_version": "0.1",
        "scenario_id": scenario_id,
        "title": f"{scenario_id} title",
        "version": "1.0",
        "world_preset": {"preset_id": preset_id},
        "initial_state": {"avatars": [], "relationships": [], "sects": []},
    }


def _timeline_payload() -> dict:
    return {"schema_version": "0.1", "events": []}


def _zip_scenario(
    scenario_id: str,
    *,
    scenario: dict | str | None = None,
    timeline: dict | str | None = None,
    extra: list[tuple[str, bytes | str | zipfile.ZipInfo]] | None = None,
) -> bytes:
    scenario = _scenario_payload(scenario_id) if scenario is None else scenario
    timeline = _timeline_payload() if timeline is None else timeline
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if scenario is not False:
            raw = scenario if isinstance(scenario, str) else json.dumps(scenario)
            zf.writestr(f"{scenario_id}/scenario.json", raw)
        if timeline is not False:
            raw = timeline if isinstance(timeline, str) else json.dumps(timeline)
            zf.writestr(f"{scenario_id}/timeline.json", raw)
        for name, payload in extra or []:
            if isinstance(payload, zipfile.ZipInfo):
                zf.writestr(payload, b"")
            else:
                zf.writestr(name, payload)
    return buffer.getvalue()


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


def test_valid_zip_import_extracted_and_registry_shows_installed():
    result = import_scenario_zip(_zip_scenario("custom_valid"))

    installed_dir = get_data_paths().root / "scenarios" / "custom_valid"
    assert result.scenario_id == "custom_valid"
    assert (installed_dir / "scenario.json").is_file()

    by_id = {scenario.id: scenario for scenario in list_installed_scenarios()}
    assert by_id["custom_valid"].source == "installed"
    assert by_id["custom_valid"].enabled is True


def test_bad_scenario_json_rejected_with_descriptive_error():
    try:
        import_scenario_zip(_zip_scenario("bad_json", scenario="{"))
    except ScenarioImportError as exc:
        assert exc.status_code == 400
        assert "Invalid JSON in scenario.json" in str(exc)
    else:
        raise AssertionError("bad scenario.json should fail import")


def test_missing_required_field_rejected():
    scenario = _scenario_payload("missing_required")
    del scenario["world_preset"]

    try:
        import_scenario_zip(_zip_scenario("missing_required", scenario=scenario))
    except ScenarioImportError as exc:
        assert exc.status_code == 400
        assert "scenario.world_preset" in str(exc)
    else:
        raise AssertionError("missing required field should fail import")


def test_scenario_id_collision_with_bundled_rejected():
    try:
        import_scenario_zip(_zip_scenario("liuchao"))
    except ScenarioImportError as exc:
        assert exc.status_code == 400
        assert exc.code == "scenario_import_bundled_collision"
    else:
        raise AssertionError("bundled collision should fail import")


def test_scenario_id_collision_with_user_installed_returns_409_conflict_shape():
    import_scenario_zip(_zip_scenario("duplicate_custom"))

    try:
        import_scenario_zip(_zip_scenario("duplicate_custom"))
    except ScenarioImportError as exc:
        assert exc.status_code == 409
        assert exc.code == "scenario_import_conflict"
        assert exc.details["scenario_id"] == "duplicate_custom"
        assert exc.details["actions"] == ["overwrite", "rename", "cancel"]
    else:
        raise AssertionError("user-installed collision should return conflict")


def test_user_installed_collision_can_be_renamed():
    import_scenario_zip(_zip_scenario("rename_custom"))

    result = import_scenario_zip(_zip_scenario("rename_custom"), rename_to="rename_custom_2")

    assert result.scenario_id == "rename_custom_2"
    by_id = {scenario.id: scenario for scenario in list_installed_scenarios()}
    assert {"rename_custom", "rename_custom_2"}.issubset(by_id)


def test_remove_user_installed_ok_and_remove_bundled_rejected():
    import_scenario_zip(_zip_scenario("remove_custom"))
    client = _command_client()

    removed = client.post("/api/v1/command/scenario/remove", json={"scenario_id": "remove_custom"})
    assert removed.status_code == 200
    assert not (get_data_paths().root / "scenarios" / "remove_custom").exists()

    bundled = client.post("/api/v1/command/scenario/remove", json={"scenario_id": "liuchao"})
    assert bundled.status_code == 400
    assert bundled.json()["detail"]["code"] == "scenario_remove_bundled"


def test_set_enabled_false_registry_returns_disabled():
    import_scenario_zip(_zip_scenario("toggle_custom"))
    client = _command_client()

    response = client.post(
        "/api/v1/command/scenario/set-enabled",
        json={"scenario_id": "toggle_custom", "enabled": False},
    )

    assert response.status_code == 200
    by_id = {scenario.id: scenario for scenario in list_installed_scenarios()}
    assert by_id["toggle_custom"].enabled is False


def test_zip_bomb_rejected():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bomb/scenario.json", json.dumps(_scenario_payload("bomb")))
        zf.writestr("bomb/timeline.json", json.dumps(_timeline_payload()))
        zf.writestr("bomb/payload.bin", b"0" * (2 * 1024 * 1024))

    try:
        import_scenario_zip(buffer.getvalue())
    except ScenarioImportError as exc:
        assert exc.code == "scenario_import_zip_bomb"
    else:
        raise AssertionError("zip bomb should fail import")


def test_path_traversal_rejected():
    try:
        import_scenario_zip(_zip_scenario("traversal", extra=[("../etc/passwd", "x")]))
    except ScenarioImportError as exc:
        assert "Unsafe zip entry path" in str(exc)
    else:
        raise AssertionError("path traversal should fail import")


def test_symlink_entry_rejected():
    symlink = zipfile.ZipInfo("symlink_case/link")
    symlink.external_attr = (stat.S_IFLNK | 0o777) << 16

    try:
        import_scenario_zip(_zip_scenario("symlink_case", extra=[("symlink_case/link", symlink)]))
    except ScenarioImportError as exc:
        assert "symlink" in str(exc)
    else:
        raise AssertionError("symlink should fail import")


def test_import_endpoint_caps_upload_at_10mb():
    client = _command_client()
    oversized = b"x" * (10 * 1024 * 1024 + 1)

    response = client.post(
        "/api/v1/command/scenario/import",
        files={"file": ("scenario.zip", oversized, "application/zip")},
    )

    assert response.status_code == 413
