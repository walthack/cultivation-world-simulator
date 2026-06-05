from __future__ import annotations

import copy
import io
import json
import zipfile
from pathlib import Path
from typing import Any

from src.scenario.scenario_fingerprint import compute_scenario_fingerprint
from src.server.services.scenario_import import ScenarioImportError
from src.server.services.scenario_repository import load_scenario_package_data, scenarios_root


def _scenario_dir(scenario_id: str) -> Path:
    scenario_dir = scenarios_root() / scenario_id
    if not scenario_dir.is_dir():
        raise ScenarioImportError(
            f"Installed scenario {scenario_id!r} was not found",
            status_code=404,
            code="scenario_export_not_found",
            details={"scenario_id": scenario_id},
        )
    return scenario_dir


def _zip_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def export_scenario(scenario_id: str) -> bytes:
    scenario_dir = _scenario_dir(scenario_id)
    scenario, timeline = load_scenario_package_data(scenario_dir)
    fingerprint = compute_scenario_fingerprint(scenario, timeline)
    exported_scenario = copy.deepcopy(scenario)
    exported_scenario["fingerprint"] = fingerprint

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{scenario_id}/scenario.json", _zip_json(exported_scenario))
        zf.writestr(f"{scenario_id}/timeline.json", _zip_json(timeline))
        for path in sorted(item for item in scenario_dir.rglob("*") if item.is_file()):
            relative = path.relative_to(scenario_dir)
            if relative.as_posix() in {"scenario.json", "timeline.json", "scenario_state.json"}:
                continue
            zf.write(path, f"{scenario_id}/{relative.as_posix()}")
    return buffer.getvalue()
