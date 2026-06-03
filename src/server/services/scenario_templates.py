from __future__ import annotations

import base64
import io
import json
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.config.data_paths import get_data_paths
from src.scenario.scenario_loader import (
    SCENARIO_ID_RE,
    ScenarioValidationError,
    get_project_root,
    validate_scenario_dir,
)
from src.server.services import scenario_state
from src.server.services.scenario_import import ScenarioImportError


@dataclass(frozen=True, slots=True)
class TemplateMeta:
    category: str
    summary: str
    title: str
    scenario_id: str
    preset_id: str

    def model_dump(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "summary": self.summary,
            "title": self.title,
            "scenario_id": self.scenario_id,
            "preset_id": self.preset_id,
        }


def _templates_root() -> Path:
    return get_project_root() / "config" / "templates" / "scenario"


def _template_path(category: str) -> Path:
    normalized = str(category).strip().lower()
    if not SCENARIO_ID_RE.match(normalized):
        raise ScenarioImportError(
            f"Invalid scenario template category: {category}",
            code="scenario_template_invalid_category",
            details={"category": category},
        )
    return _templates_root() / f"{normalized}.json"


def _load_template_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ScenarioImportError(
            f"Scenario template {path.stem!r} was not found",
            status_code=404,
            code="scenario_template_not_found",
            details={"category": path.stem},
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ScenarioImportError(f"Invalid JSON in template {path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise ScenarioImportError(f"Scenario template {path.name} must contain an object")
    return data


def _scenario_from_draft(draft: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    scenario = draft.get("scenario")
    timeline = draft.get("timeline")
    if scenario is None:
        scenario = {key: value for key, value in draft.items() if key != "timeline"}
    if timeline is None:
        timeline = {"schema_version": str(scenario.get("schema_version", "0.1")), "events": []}
    if not isinstance(scenario, dict):
        raise ScenarioImportError("scenario draft must contain a scenario object")
    if not isinstance(timeline, dict):
        raise ScenarioImportError("scenario draft must contain a timeline object")
    return scenario, timeline


def _validate_draft(scenario: dict[str, Any], timeline: dict[str, Any]) -> list[str]:
    scenario_id = str(scenario.get("scenario_id", "")).strip()
    if not SCENARIO_ID_RE.match(scenario_id):
        raise ScenarioImportError(
            f"Invalid scenario id: {scenario_id}",
            code="scenario_draft_invalid_id",
            details={"scenario_id": scenario_id},
        )
    data_root = get_data_paths().root
    data_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="scenario-draft-", dir=str(data_root)) as tmp_name:
        scenario_dir = Path(tmp_name) / scenario_id
        scenario_dir.mkdir(parents=True, exist_ok=True)
        (scenario_dir / "scenario.json").write_text(
            json.dumps(scenario, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (scenario_dir / "timeline.json").write_text(
            json.dumps(timeline, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        try:
            validation = validate_scenario_dir(scenario_dir)
        except ScenarioValidationError as exc:
            raise ScenarioImportError(str(exc), details={"path": exc.path}) from exc
    return validation.warnings


def _zip_draft(scenario_id: str, scenario: dict[str, Any], timeline: dict[str, Any]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            f"{scenario_id}/scenario.json",
            json.dumps(scenario, ensure_ascii=False, indent=2),
        )
        zf.writestr(
            f"{scenario_id}/timeline.json",
            json.dumps(timeline, ensure_ascii=False, indent=2),
        )
    return buffer.getvalue()


def list_templates() -> list[TemplateMeta]:
    templates: list[TemplateMeta] = []
    for path in sorted(_templates_root().glob("*.json")):
        data = _load_template_file(path)
        scenario, _timeline = _scenario_from_draft(data)
        world_preset = scenario.get("world_preset") if isinstance(scenario.get("world_preset"), dict) else {}
        templates.append(
            TemplateMeta(
                category=str(data.get("category") or path.stem),
                summary=str(data.get("summary") or scenario.get("description") or ""),
                title=str(scenario.get("title") or path.stem),
                scenario_id=str(scenario.get("scenario_id") or ""),
                preset_id=str(world_preset.get("preset_id") or ""),
            )
        )
    return templates


def load_template(category: str) -> dict[str, Any]:
    return _load_template_file(_template_path(category))


def save_draft(draft: dict[str, Any]) -> dict[str, Any]:
    scenario, timeline = _scenario_from_draft(draft)
    warnings = _validate_draft(scenario, timeline)
    scenario_id = str(scenario["scenario_id"])
    bundled_target = get_project_root() / "config" / "scenarios" / scenario_id
    if bundled_target.is_dir():
        raise ScenarioImportError(
            f"Bundled scenario {scenario_id!r} cannot be overwritten",
            code="scenario_draft_bundled_collision",
            details={"scenario_id": scenario_id, "source": "bundled"},
        )

    installed_root = get_data_paths().root / "scenarios"
    installed_root.mkdir(parents=True, exist_ok=True)
    target = installed_root / scenario_id
    tmp_target = installed_root / f".{scenario_id}.draft-tmp"
    if tmp_target.exists():
        shutil.rmtree(tmp_target)
    tmp_target.mkdir(parents=True)
    (tmp_target / "scenario.json").write_text(
        json.dumps(scenario, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (tmp_target / "timeline.json").write_text(
        json.dumps(timeline, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if target.exists():
        shutil.rmtree(target)
    tmp_target.replace(target)
    scenario_state.set_enabled(scenario_id, True)

    zip_bytes = _zip_draft(scenario_id, scenario, timeline)
    return {
        "status": "saved",
        "scenario_id": scenario_id,
        "path": str(target),
        "warnings": warnings,
        "zip_filename": f"{scenario_id}.zip",
        "zip_mime": "application/zip",
        "zip_base64": base64.b64encode(zip_bytes).decode("ascii"),
    }
