from __future__ import annotations

import io
import json
import os
import shutil
import stat
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from src.config.data_paths import get_data_paths
from src.scenario.scenario_loader import (
    SCENARIO_ID_RE,
    ScenarioValidationError,
    get_project_root,
    validate_scenario_dir,
)
from src.server.services import scenario_state


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024


class ScenarioImportError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int = 400,
        code: str = "scenario_import_invalid",
        details: dict[str, Any] | None = None,
    ):
        self.status_code = status_code
        self.code = code
        self.details = details or {}
        super().__init__(message)


@dataclass(slots=True)
class ImportResult:
    status: str
    scenario_id: str | None = None
    name: str | None = None
    version: str | None = None
    source: str = "installed"
    enabled: bool = True
    warnings: list[str] = field(default_factory=list)
    conflict: dict[str, Any] | None = None

    def model_dump(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "scenario_id": self.scenario_id,
            "name": self.name,
            "version": self.version,
            "source": self.source,
            "enabled": self.enabled,
            "warnings": list(self.warnings),
            "conflict": self.conflict,
        }


def _installed_root() -> Path:
    root = get_data_paths().root / "scenarios"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _bundled_root() -> Path:
    return get_project_root() / "config" / "scenarios"


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0o170000
    return mode == stat.S_IFLNK


def _safe_entry_parts(name: str) -> tuple[str, ...]:
    path = PurePosixPath(name)
    parts = path.parts
    if not parts or path.is_absolute() or any(part in {"", ".", ".."} for part in parts):
        raise ScenarioImportError(f"Unsafe zip entry path: {name}")
    return parts


def _is_inside(child: Path, root: Path) -> bool:
    child_resolved = child.resolve()
    root_resolved = root.resolve()
    root_text = str(root_resolved)
    child_text = str(child_resolved)
    return child_text == root_text or child_text.startswith(root_text + os.sep)


def _inspect_zip(zip_bytes: bytes, max_size: int) -> tuple[list[zipfile.ZipInfo], str]:
    if len(zip_bytes) > max_size:
        raise ScenarioImportError(
            f"Scenario package exceeds {max_size} bytes",
            code="scenario_import_upload_too_large",
        )

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            infos = zf.infolist()
            bad_file = zf.testzip()
            if bad_file is not None:
                raise ScenarioImportError(f"Invalid zip entry checksum: {bad_file}")
    except zipfile.BadZipFile as exc:
        raise ScenarioImportError("Scenario package is not a valid zip file") from exc

    if not infos:
        raise ScenarioImportError("Scenario package is empty")

    total_uncompressed = 0
    roots: set[str] = set()
    for info in infos:
        if _is_symlink(info):
            raise ScenarioImportError(f"Zip entry is a symlink: {info.filename}")
        parts = _safe_entry_parts(info.filename)
        roots.add(parts[0])
        if not info.is_dir():
            total_uncompressed += int(info.file_size)

    compressed_cap = max(1, len(zip_bytes)) * 100
    if total_uncompressed > compressed_cap or total_uncompressed > MAX_UNCOMPRESSED_BYTES:
        raise ScenarioImportError(
            "Scenario package exceeds zip-bomb safety limits",
            code="scenario_import_zip_bomb",
            details={
                "uncompressed_bytes": total_uncompressed,
                "compressed_bytes": len(zip_bytes),
                "ratio_cap_bytes": compressed_cap,
                "absolute_cap_bytes": MAX_UNCOMPRESSED_BYTES,
            },
        )

    if len(roots) != 1:
        raise ScenarioImportError("Scenario package must contain exactly one top-level scenario directory")
    scenario_id = next(iter(roots))
    if not SCENARIO_ID_RE.match(scenario_id):
        raise ScenarioImportError(f"Invalid scenario directory name: {scenario_id}")
    return infos, scenario_id


def _extract_checked(zip_bytes: bytes, infos: list[zipfile.ZipInfo], scenario_id: str, tmp_root: Path) -> Path:
    scenario_dir = tmp_root / scenario_id
    scenario_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for info in infos:
            parts = _safe_entry_parts(info.filename)
            if parts[0] != scenario_id:
                raise ScenarioImportError("Zip entries must stay inside the scenario directory")
            target = tmp_root.joinpath(*parts)
            if not _is_inside(target, scenario_dir):
                raise ScenarioImportError(f"Zip entry escapes scenario directory: {info.filename}")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as source, target.open("wb") as dest:
                shutil.copyfileobj(source, dest)
    return scenario_dir


def _ensure_package_files(scenario_dir: Path) -> None:
    for filename in ("scenario.json", "timeline.json"):
        path = scenario_dir / filename
        if not path.is_file():
            raise ScenarioImportError(f"Scenario package is missing {filename}")
        try:
            with path.open("r", encoding="utf-8") as handle:
                parsed = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ScenarioImportError(f"Invalid JSON in {filename}: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ScenarioImportError(f"{filename} must contain a JSON object")


def _install_validated_dir(scenario_dir: Path, scenario_id: str, *, force: bool) -> Path:
    installed_root = _installed_root()
    bundled_target = _bundled_root() / scenario_id
    if bundled_target.is_dir():
        raise ScenarioImportError(
            f"Scenario id {scenario_id!r} is bundled and cannot be overwritten",
            code="scenario_import_bundled_collision",
            details={"scenario_id": scenario_id, "source": "bundled"},
        )

    target = installed_root / scenario_id
    if target.exists() and not force:
        raise ScenarioImportError(
            f"Scenario id {scenario_id!r} is already installed",
            status_code=409,
            code="scenario_import_conflict",
            details={
                "scenario_id": scenario_id,
                "actions": ["overwrite", "rename", "cancel"],
            },
        )

    backup: Path | None = None
    if target.exists():
        backup = installed_root / f".{scenario_id}.replace-backup"
        if backup.exists():
            shutil.rmtree(backup)
        target.replace(backup)

    try:
        scenario_dir.replace(target)
    except Exception:
        if backup is not None and backup.exists() and not target.exists():
            backup.replace(target)
        raise
    else:
        if backup is not None and backup.exists():
            shutil.rmtree(backup)
    return target


def _rename_validated_dir(scenario_dir: Path, scenario_id: str, rename_to: str | None) -> tuple[Path, str]:
    if not rename_to:
        return scenario_dir, scenario_id
    if not SCENARIO_ID_RE.match(rename_to):
        raise ScenarioImportError(f"Invalid rename scenario id: {rename_to}")
    if rename_to == scenario_id:
        return scenario_dir, scenario_id

    renamed_dir = scenario_dir.parent / rename_to
    if renamed_dir.exists():
        raise ScenarioImportError(f"Temporary renamed scenario directory already exists: {rename_to}")
    scenario_dir.replace(renamed_dir)
    scenario_path = renamed_dir / "scenario.json"
    with scenario_path.open("r", encoding="utf-8") as handle:
        scenario = json.load(handle)
    if not isinstance(scenario, dict):
        raise ScenarioImportError("scenario.json must contain a JSON object")
    scenario["scenario_id"] = rename_to
    scenario_path.write_text(json.dumps(scenario, ensure_ascii=False, indent=2), encoding="utf-8")
    return renamed_dir, rename_to


def import_scenario_zip(
    zip_bytes: bytes,
    *,
    max_size: int = MAX_UPLOAD_BYTES,
    force: bool = False,
    rename_to: str | None = None,
) -> ImportResult:
    infos, scenario_id = _inspect_zip(zip_bytes, max_size)
    with tempfile.TemporaryDirectory(prefix="scenario-import-", dir=str(get_data_paths().root)) as tmp_name:
        tmp_root = Path(tmp_name)
        scenario_dir = _extract_checked(zip_bytes, infos, scenario_id, tmp_root)
        _ensure_package_files(scenario_dir)
        try:
            validation = validate_scenario_dir(scenario_dir)
        except ScenarioValidationError as exc:
            raise ScenarioImportError(str(exc), details={"path": exc.path}) from exc

        scenario_dir, scenario_id = _rename_validated_dir(
            scenario_dir,
            validation.scenario_id,
            rename_to,
        )
        if scenario_id != validation.scenario_id:
            try:
                validation = validate_scenario_dir(scenario_dir)
            except ScenarioValidationError as exc:
                raise ScenarioImportError(str(exc), details={"path": exc.path}) from exc

        installed_dir = _install_validated_dir(scenario_dir, validation.scenario_id, force=force)
        scenario_state.set_enabled(validation.scenario_id, True)
        return ImportResult(
            status="imported",
            scenario_id=validation.scenario_id,
            name=validation.title,
            version=validation.version,
            source="installed",
            enabled=True,
            warnings=validation.warnings,
        )


def remove_installed_scenario(scenario_id: str) -> dict[str, Any]:
    if not SCENARIO_ID_RE.match(scenario_id):
        raise ScenarioImportError(f"Invalid scenario id: {scenario_id}")
    if (_bundled_root() / scenario_id).is_dir():
        raise ScenarioImportError(
            f"Bundled scenario {scenario_id!r} cannot be removed",
            code="scenario_remove_bundled",
            details={"scenario_id": scenario_id, "source": "bundled"},
        )

    target = _installed_root() / scenario_id
    if not target.exists():
        raise ScenarioImportError(
            f"Installed scenario {scenario_id!r} was not found",
            status_code=404,
            code="scenario_remove_not_found",
            details={"scenario_id": scenario_id},
        )
    shutil.rmtree(target)
    scenario_state.remove(scenario_id)
    return {"scenario_id": scenario_id, "removed": True}
