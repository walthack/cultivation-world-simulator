from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.config.data_paths import get_data_paths
from src.scenario.scenario_fingerprint import compute_scenario_fingerprint
from src.scenario.scenario_loader import SCHEMA_VERSION, SUPPORTED_SCHEMA_VERSIONS, ScenarioValidationError, validate_scenario_dir
from src.server.services import scenario_state
from src.server.services.scenario_compat import CompatResult, check_compatibility, compare_lenient_semver
from src.server.services.scenario_import import ScenarioImportError


@dataclass(slots=True)
class VerificationDTO:
    status: str
    computed: str
    claimed: str | None = None

    def model_dump(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "computed": self.computed,
            "claimed": self.claimed,
        }


@dataclass(slots=True)
class RepositoryScenarioDTO:
    id: str
    download_id: str | None
    name: str
    version: str
    author: str | None = None
    description: str = ""
    tags: list[str] = field(default_factory=list)
    cover_image: str | None = None
    source: str = "installed"
    enabled: bool = True
    fingerprint: str | None = None
    verification: VerificationDTO | None = None
    compatibility: dict[str, Any] | None = None

    def model_dump(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "download_id": self.download_id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "tags": list(self.tags),
            "cover_image": self.cover_image,
            "source": self.source,
            "enabled": self.enabled,
            "fingerprint": self.fingerprint,
            "verification": self.verification.model_dump() if self.verification is not None else None,
            "compatibility": self.compatibility,
        }


@dataclass(slots=True)
class RepositoryUpdateDTO:
    installed: RepositoryScenarioDTO
    downloaded: RepositoryScenarioDTO

    def model_dump(self) -> dict[str, Any]:
        return {
            "installed": self.installed.model_dump(),
            "downloaded": self.downloaded.model_dump(),
        }


@dataclass(slots=True)
class RepositoryDTO:
    installed: list[RepositoryScenarioDTO] = field(default_factory=list)
    downloaded: list[RepositoryScenarioDTO] = field(default_factory=list)
    updates: list[RepositoryUpdateDTO] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        return {
            "installed": [item.model_dump() for item in self.installed],
            "downloaded": [item.model_dump() for item in self.downloaded],
            "updates": [item.model_dump() for item in self.updates],
        }


def scenarios_root() -> Path:
    root = get_data_paths().root / "scenarios"
    root.mkdir(parents=True, exist_ok=True)
    return root


def downloads_root() -> Path:
    root = get_data_paths().root / "scenarios_downloads"
    root.mkdir(parents=True, exist_ok=True)
    return root


def archive_root() -> Path:
    root = get_data_paths().root / "scenarios_archive"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _current_cws_version() -> str:
    config_path = Path(__file__).resolve().parents[3] / "static" / "config.yml"
    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError:
        return "0.0.0"
    match = re.search(r"^\s*version:\s*[\"']?([^\"'\n]+)", text, re.MULTILINE)
    return match.group(1).strip() if match else "0.0.0"


def load_scenario_package_data(scenario_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    scenario_path = scenario_dir / "scenario.json"
    timeline_path = scenario_dir / "timeline.json"
    try:
        scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
        timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ScenarioImportError(f"Invalid scenario package JSON: {exc}") from exc
    except OSError as exc:
        raise ScenarioImportError(f"Scenario package is missing required files: {scenario_dir}") from exc
    if not isinstance(scenario, dict) or not isinstance(timeline, dict):
        raise ScenarioImportError("scenario.json and timeline.json must contain objects")
    return scenario, timeline


def compute_verification(scenario: dict[str, Any], timeline: dict[str, Any]) -> VerificationDTO:
    claimed = scenario.get("fingerprint")
    computed = compute_scenario_fingerprint(scenario, timeline)
    if not isinstance(claimed, str) or not claimed:
        return VerificationDTO(status="unsigned", computed=computed, claimed=None)
    if claimed == computed:
        return VerificationDTO(status="verified", computed=computed, claimed=claimed)
    return VerificationDTO(status="modified", computed=computed, claimed=claimed)


def _metadata_from_dir(scenario_dir: Path, *, source: str, enabled: bool) -> RepositoryScenarioDTO | None:
    try:
        scenario, timeline = load_scenario_package_data(scenario_dir)
    except ScenarioImportError:
        return None
    scenario_id = scenario.get("scenario_id")
    title = scenario.get("title")
    version = scenario.get("version")
    if not all(isinstance(value, str) and value.strip() for value in (scenario_id, title, version)):
        return None
    tags = scenario.get("tags", [])
    if not isinstance(tags, list):
        tags = []
    cover_image = scenario.get("cover_image")
    author = scenario.get("author")
    verification = compute_verification(scenario, timeline)
    compat = check_compatibility(scenario, _current_cws_version(), SUPPORTED_SCHEMA_VERSIONS).model_dump()
    return RepositoryScenarioDTO(
        id=scenario_id,
        download_id=scenario_dir.name if source == "downloaded" else None,
        name=title,
        version=version,
        author=author if isinstance(author, str) and author.strip() else None,
        description=scenario.get("description", "") if isinstance(scenario.get("description", ""), str) else "",
        tags=[str(item) for item in tags if isinstance(item, str) and item.strip()],
        cover_image=cover_image if isinstance(cover_image, str) and cover_image.strip() else None,
        source=source,
        enabled=enabled,
        fingerprint=verification.claimed or verification.computed,
        verification=verification,
        compatibility=compat,
    )


def _scan_root(root: Path, *, source: str) -> list[RepositoryScenarioDTO]:
    if not root.is_dir():
        return []
    state = scenario_state.get_state()
    items: list[RepositoryScenarioDTO] = []
    for scenario_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        enabled = bool(state.get(scenario_dir.name, {}).get("enabled", True))
        meta = _metadata_from_dir(scenario_dir, source=source, enabled=enabled)
        if meta is not None:
            items.append(meta)
    return items


def list_repository() -> RepositoryDTO:
    installed = _scan_root(scenarios_root(), source="installed")
    downloaded = _scan_root(downloads_root(), source="downloaded")
    updates: list[RepositoryUpdateDTO] = []
    installed_by_id = {item.id: item for item in installed}
    for downloaded_item in downloaded:
        installed_item = installed_by_id.get(downloaded_item.id)
        if installed_item is None:
            continue
        comparison = compare_lenient_semver(downloaded_item.version, installed_item.version)
        if comparison is not None and comparison > 0:
            updates.append(RepositoryUpdateDTO(installed=installed_item, downloaded=downloaded_item))
    return RepositoryDTO(installed=installed, downloaded=downloaded, updates=updates)


def _download_dir(download_id: str) -> Path:
    if not re.match(r"^[A-Za-z0-9_.-]+$", str(download_id)):
        raise ScenarioImportError(f"Invalid download id: {download_id}", code="scenario_download_invalid_id")
    path = downloads_root() / download_id
    if not path.is_dir():
        raise ScenarioImportError(
            f"Downloaded scenario {download_id!r} was not found",
            status_code=404,
            code="scenario_download_not_found",
            details={"download_id": download_id},
        )
    return path


def _validate_and_check(scenario_dir: Path) -> tuple[dict[str, Any], CompatResult]:
    try:
        validation = validate_scenario_dir(scenario_dir)
    except ScenarioValidationError as exc:
        raise ScenarioImportError(str(exc), details={"path": exc.path}) from exc
    scenario, _timeline = load_scenario_package_data(scenario_dir)
    compat = check_compatibility(scenario, _current_cws_version(), SUPPORTED_SCHEMA_VERSIONS)
    if compat.status == "fail":
        raise ScenarioImportError(
            "Scenario compatibility check failed",
            code="scenario_compat_failed",
            details={"compatibility": compat.model_dump(), "scenario_id": validation.scenario_id},
        )
    return scenario, compat


def install_from_download(download_id: str, *, confirm_warnings: bool = False) -> dict[str, Any]:
    source = _download_dir(download_id)
    scenario, compat = _validate_and_check(source)
    scenario_id = str(scenario["scenario_id"])
    if compat.status == "warn" and not confirm_warnings:
        return {"status": "warning", "moved": False, "scenario_id": scenario_id, "compatibility": compat.model_dump()}
    target = scenarios_root() / scenario_id
    if target.exists():
        raise ScenarioImportError(
            f"Scenario id {scenario_id!r} is already installed",
            status_code=409,
            code="scenario_install_conflict",
            details={"scenario_id": scenario_id},
        )
    source.replace(target)
    scenario_state.set_enabled(scenario_id, True)
    return {"status": "installed", "moved": True, "scenario_id": scenario_id, "compatibility": compat.model_dump()}


def update_from_download(
    installed_scenario_id: str,
    download_id: str,
    *,
    confirm_warnings: bool = False,
) -> dict[str, Any]:
    target = scenarios_root() / installed_scenario_id
    if not target.is_dir():
        raise ScenarioImportError(
            f"Installed scenario {installed_scenario_id!r} was not found",
            status_code=404,
            code="scenario_update_installed_not_found",
            details={"scenario_id": installed_scenario_id},
        )
    source = _download_dir(download_id)
    scenario, compat = _validate_and_check(source)
    scenario_id = str(scenario["scenario_id"])
    if scenario_id != installed_scenario_id:
        raise ScenarioImportError(
            "Downloaded scenario id does not match installed scenario id",
            code="scenario_update_id_mismatch",
            details={"installed_scenario_id": installed_scenario_id, "downloaded_scenario_id": scenario_id},
        )
    if compat.status == "warn" and not confirm_warnings:
        return {"status": "warning", "moved": False, "scenario_id": scenario_id, "compatibility": compat.model_dump()}

    installed_scenario, _timeline = load_scenario_package_data(target)
    old_version = str(installed_scenario.get("version") or "unknown")
    archive_dir = archive_root() / installed_scenario_id / old_version
    if archive_dir.exists():
        shutil.rmtree(archive_dir)
    archive_dir.parent.mkdir(parents=True, exist_ok=True)
    target.replace(archive_dir)
    try:
        source.replace(target)
    except Exception:
        if archive_dir.exists() and not target.exists():
            archive_dir.replace(target)
        raise
    scenario_state.set_enabled(scenario_id, True)
    return {
        "status": "updated",
        "moved": True,
        "scenario_id": scenario_id,
        "archived_to": str(archive_dir),
        "compatibility": compat.model_dump(),
    }
