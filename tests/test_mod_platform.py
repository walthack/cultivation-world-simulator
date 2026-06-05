from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.config.data_paths import reset_data_paths_cache
from src.config.settings_service import get_settings_service
from src.i18n import t
from src.mod_platform.asset_overlay import resolve_asset
from src.mod_platform.locale_overlay import translate
from src.mod_platform.mod_conflict import ModConflictError
from src.mod_platform.mod_import import compute_mod_fingerprint, install_mod_folder, install_mod_zip, uninstall_mod
from src.mod_platform.mod_loader import get_active_extensions, load_enabled_mods
from src.mod_platform.mod_registry import list_installed_mods, set_enabled
from src.mod_platform.python_hooks import dispatch_lifecycle_hook
from src.scenario.condition_evaluator import ConditionEvaluationError, evaluate_condition


@pytest.fixture()
def mod_data_root(tmp_path, monkeypatch):
    monkeypatch.setenv("CWS_DATA_DIR", str(tmp_path))
    reset_data_paths_cache()
    get_settings_service.cache_clear()
    yield tmp_path
    reset_data_paths_cache()
    get_settings_service.cache_clear()


def _write_mod(root: Path, mod_id: str, *, predicate: str | None = None, dependency: str | None = None) -> Path:
    mod_dir = root / mod_id
    (mod_dir / "assets" / "avatars" / "male" / "999").mkdir(parents=True)
    (mod_dir / "llm").mkdir(parents=True)
    (mod_dir / "locale").mkdir(parents=True)
    (mod_dir / "rules").mkdir(parents=True)
    (mod_dir / "code").mkdir(parents=True)
    (mod_dir / "assets" / "avatars" / "male" / "999" / "qi_refining.png").write_text("png", encoding="utf-8")
    (mod_dir / "llm" / "npc_action.txt").write_text("mod template {name}", encoding="utf-8")
    (mod_dir / "locale" / "en_US.json").write_text(json.dumps({"mod.hello": "Hello from mod"}), encoding="utf-8")
    if predicate:
        (mod_dir / "rules" / "predicates.py").write_text(
            f"def {predicate}(state, args):\n    return bool(args.get('ok', True))\n",
            encoding="utf-8",
        )
    (mod_dir / "code" / "lifecycle.py").write_text(
        "def on_world_init(world):\n    world.hook_fired = True\n",
        encoding="utf-8",
    )
    payload = {
        "mod_id": mod_id,
        "name": mod_id,
        "version": "1.0.0",
        "author": "tester",
        "description": "test mod",
        "fingerprint": "",
        "dependencies": ([{"type": "mod", "id": dependency}] if dependency else []),
        "extensions": {
            "rules": {"predicates": [predicate] if predicate else [], "effects": []},
            "assets": {
                "portraits": ["avatars/male/999/qi_refining.png"],
                "icons": [],
                "localizations": {"en-US": "locale/en_US.json"},
            },
            "llm": {"prompts": [{"key": "npc_action", "template_path": "llm/npc_action.txt"}]},
            "code": {"hooks": ["on_world_init"]},
        },
    }
    (mod_dir / "mod.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    payload["fingerprint"] = compute_mod_fingerprint(mod_dir)
    (mod_dir / "mod.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return mod_dir


def _zip_mod(mod_dir: Path) -> bytes:
    archive = mod_dir.parent / f"{mod_dir.name}.mod"
    with zipfile.ZipFile(archive, "w") as zf:
        for path in mod_dir.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(mod_dir))
    return archive.read_bytes()


def test_install_valid_mod_zip_registry_shows_it_and_scenarios_still_work(mod_data_root, tmp_path):
    source = _write_mod(tmp_path, "zip-mod", predicate="zip_predicate")
    result = install_mod_zip(_zip_mod(source))
    assert result["mod_id"] == "zip-mod"
    assert [mod.mod_id for mod in list_installed_mods()] == ["zip-mod"]
    assert evaluate_condition({}, {"always": {"value": True}}) is True


def test_asset_overlay_resolves_mod_png_before_bundled(mod_data_root, tmp_path):
    source = _write_mod(tmp_path, "asset-mod")
    install_mod_folder(source)
    bundled = tmp_path / "bundled"
    load_enabled_mods(settings_view=SimpleNamespace(allow_trusted_python_mods=False), bundled_assets_root=bundled)
    resolved = resolve_asset("avatars/male/999/qi_refining.png", bundled)
    assert resolved.read_text(encoding="utf-8") == "png"


@pytest.mark.asyncio
async def test_llm_prompt_overlay_uses_mod_template(monkeypatch, mod_data_root, tmp_path):
    source = _write_mod(tmp_path, "llm-mod")
    install_mod_folder(source)
    load_enabled_mods(settings_view=SimpleNamespace(allow_trusted_python_mods=False))
    captured = {}

    async def fake_json(prompt, mode, max_retries):
        captured["prompt"] = prompt
        return {"ok": True}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", fake_json)
    from src.utils.llm.client import call_llm_with_template
    result = await call_llm_with_template("npc_action", {"name": "A"})
    assert result == {"ok": True}
    assert captured["prompt"] == "mod template A"


def test_localization_overlay_returns_mod_string(mod_data_root, tmp_path):
    source = _write_mod(tmp_path, "locale-mod")
    install_mod_folder(source)
    load_enabled_mods(settings_view=SimpleNamespace(allow_trusted_python_mods=False))
    assert translate("en-US", "mod.hello") == "Hello from mod"
    assert t("mod.hello") in {"Hello from mod", "mod.hello"}


def test_custom_predicate_inert_when_python_gate_off(mod_data_root, tmp_path):
    source = _write_mod(tmp_path, "python-off-mod", predicate="custom_gate_predicate")
    install_mod_folder(source)
    load_enabled_mods(settings_view=SimpleNamespace(allow_trusted_python_mods=False))
    with pytest.raises(ConditionEvaluationError, match="unknown predicate"):
        evaluate_condition({}, {"custom_gate_predicate": {"ok": True}})


def test_custom_predicate_active_when_python_gate_on(mod_data_root, tmp_path):
    source = _write_mod(tmp_path, "python-on-mod", predicate="active_predicate")
    install_mod_folder(source)
    load_enabled_mods(settings_view=SimpleNamespace(allow_trusted_python_mods=True))
    assert evaluate_condition({}, {"active_predicate": {"ok": True}}) is True


def test_lifecycle_hook_fires_on_world_init_when_gate_on(mod_data_root, tmp_path):
    source = _write_mod(tmp_path, "hook-on-mod", predicate="hook_predicate")
    install_mod_folder(source)
    load_enabled_mods(settings_view=SimpleNamespace(allow_trusted_python_mods=True))
    world = SimpleNamespace()
    dispatch_lifecycle_hook("on_world_init", world)
    assert world.hook_fired is True


def test_python_gate_state_reflected_in_extensions_shape(mod_data_root, tmp_path):
    """
    Assert the safety gate's effect is observable via the same runtime data
    structure the API endpoint /api/v1/query/mods/extensions-active exposes,
    namely get_active_extensions() returning items of shape
    {kind, name, active, inert, python_required, ...}.

    OFF  → predicate extension present with active=False, inert=True
    ON   → same extension with active=True, inert=False
    """
    source = _write_mod(tmp_path, "shape-mod", predicate="shape_check_predicate")
    install_mod_folder(source)

    load_enabled_mods(settings_view=SimpleNamespace(allow_trusted_python_mods=False))
    off_entry = next(
        ext for ext in get_active_extensions()
        if ext["kind"] == "predicate" and ext["name"] == "shape_check_predicate"
    )
    assert off_entry["active"] is False
    assert off_entry["inert"] is True
    assert off_entry["python_required"] is True

    load_enabled_mods(settings_view=SimpleNamespace(allow_trusted_python_mods=True))
    on_entry = next(
        ext for ext in get_active_extensions()
        if ext["kind"] == "predicate" and ext["name"] == "shape_check_predicate"
    )
    assert on_entry["active"] is True
    assert on_entry["inert"] is False


def test_lifecycle_hook_does_not_fire_when_gate_off(mod_data_root, tmp_path):
    source = _write_mod(tmp_path, "hook-off-mod", predicate="hook_off_predicate")
    install_mod_folder(source)
    load_enabled_mods(settings_view=SimpleNamespace(allow_trusted_python_mods=False))
    world = SimpleNamespace()
    dispatch_lifecycle_hook("on_world_init", world)
    assert not hasattr(world, "hook_fired")


def test_conflict_modal_triggered_when_two_enabled_mods_declare_same_predicate(mod_data_root, tmp_path):
    install_mod_folder(_write_mod(tmp_path, "conflict-a", predicate="same_predicate"))
    install_mod_folder(_write_mod(tmp_path, "conflict-b", predicate="same_predicate"))
    with pytest.raises(ModConflictError) as exc:
        load_enabled_mods(settings_view=SimpleNamespace(allow_trusted_python_mods=True))
    # _write_mod helper also writes the same asset path per mod, so an asset conflict
    # comes ahead of the predicate conflict in exc.value.conflicts. Assert the predicate
    # conflict is present (the test's intent) regardless of order.
    assert any(c.name == "same_predicate" for c in exc.value.conflicts)


def test_dependency_check_fails_when_required_mod_is_missing(mod_data_root, tmp_path):
    source = _write_mod(tmp_path, "dependent-mod", dependency="base-mod")
    with pytest.raises(Exception, match="Required mod"):
        install_mod_folder(source)


def test_disable_mod_removes_extensions_from_runtime_registries(mod_data_root, tmp_path):
    source = _write_mod(tmp_path, "disable-mod", predicate="disable_predicate")
    install_mod_folder(source)
    load_enabled_mods(settings_view=SimpleNamespace(allow_trusted_python_mods=True))
    assert evaluate_condition({}, {"disable_predicate": {"ok": True}}) is True
    set_enabled("disable-mod", False)
    load_enabled_mods(settings_view=SimpleNamespace(allow_trusted_python_mods=True))
    with pytest.raises(ConditionEvaluationError, match="unknown predicate"):
        evaluate_condition({}, {"disable_predicate": {"ok": True}})
    uninstall_mod("disable-mod")
