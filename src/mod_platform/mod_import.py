from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from . import mod_registry


MAX_MOD_UPLOAD_BYTES = 50 * 1024 * 1024


class ModImportError(ValueError):
    def __init__(self, message: str, *, status_code: int = 400, code: str = "mod_import_error", details: dict | None = None):
        self.status_code = status_code
        self.code = code
        self.details = details or {}
        super().__init__(message)


def compute_mod_fingerprint(mod_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in mod_dir.rglob("*") if item.is_file()):
        relative = path.relative_to(mod_dir).as_posix()
        digest.update(relative.encode("utf-8"))
        if relative == "mod.json":
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    payload.pop("fingerprint", None)
                content = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            except Exception:
                content = path.read_bytes()
        else:
            content = path.read_bytes()
        digest.update(content)
    return "sha256:" + digest.hexdigest()


def validate_mod_dir(mod_dir: Path, *, installed_mod_ids: set[str] | None = None) -> dict[str, Any]:
    try:
        metadata = mod_registry.parse_mod_json(mod_dir)
    except Exception as exc:
        raise ModImportError(str(exc), code="mod_invalid_metadata") from exc

    for dependency in metadata.dependencies:
        if not isinstance(dependency, dict):
            raise ModImportError("mod dependencies must be objects", code="mod_invalid_dependency")
        dep_type = dependency.get("type")
        dep_id = dependency.get("id")
        if dep_type not in {"preset", "mod"}:
            raise ModImportError("mod dependency type must be preset or mod", code="mod_invalid_dependency")
        if not isinstance(dep_id, str) or not dep_id.strip():
            raise ModImportError("mod dependency id must be a non-empty string", code="mod_invalid_dependency")
        if dep_type == "mod" and installed_mod_ids is not None and dep_id not in installed_mod_ids:
            raise ModImportError(
                f"Required mod {dep_id!r} is not installed",
                code="mod_dependency_missing",
                details={"dependency": dependency},
            )

    expected = metadata.fingerprint
    actual = compute_mod_fingerprint(mod_dir)
    if expected and expected != actual:
        raise ModImportError(
            "mod fingerprint mismatch",
            code="mod_fingerprint_mismatch",
            details={"expected": expected, "actual": actual},
        )

    metadata.fingerprint = actual
    return metadata.to_dict()


def _copy_mod_dir(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def install_mod_folder(folder: Path) -> dict[str, Any]:
    installed_ids = {mod.mod_id for mod in mod_registry.list_installed_mods()}
    metadata_dict = validate_mod_dir(folder, installed_mod_ids=installed_ids)
    metadata = mod_registry.parse_mod_json(folder)
    metadata.fingerprint = metadata_dict["fingerprint"]
    destination = mod_registry.mods_root() / metadata.mod_id
    _copy_mod_dir(folder, destination)
    metadata.path = str(destination)
    mod_registry.upsert_mod(metadata)
    return metadata.to_dict()


def install_mod_zip(zip_bytes: bytes, *, max_size: int = MAX_MOD_UPLOAD_BYTES) -> dict[str, Any]:
    if len(zip_bytes) > max_size:
        raise ModImportError("Mod upload is too large", status_code=413, code="mod_upload_too_large")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        try:
            with zipfile.ZipFile(Path(tmp_path / "upload.mod"), "w") as _:
                pass
            archive_path = tmp_path / "upload.mod"
            archive_path.write_bytes(zip_bytes)
            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(tmp_path / "extracted")
        except zipfile.BadZipFile as exc:
            raise ModImportError("Invalid .mod archive", code="mod_invalid_zip") from exc
        extracted = tmp_path / "extracted"
        candidates = [extracted] + [item for item in extracted.iterdir() if item.is_dir()]
        for candidate in candidates:
            if (candidate / "mod.json").exists():
                return install_mod_folder(candidate)
    raise ModImportError("Mod archive must contain mod.json", code="mod_json_missing")


def uninstall_mod(mod_id: str) -> dict[str, Any]:
    target = mod_registry.mods_root() / mod_id
    if target.exists():
        shutil.rmtree(target)
    mod_registry.remove_mod(mod_id)
    return {"mod_id": mod_id}


def export_mod(mod_id: str) -> bytes:
    metadata = mod_registry.get_mod(mod_id)
    if metadata is None:
        raise ModImportError(f"Mod {mod_id!r} was not found", status_code=404, code="mod_not_found")
    mod_dir = Path(metadata.path)
    if not mod_dir.exists():
        raise ModImportError(f"Mod {mod_id!r} files were not found", status_code=404, code="mod_files_not_found")
    with tempfile.TemporaryDirectory() as tmp:
        archive_base = Path(tmp) / mod_id
        archive = shutil.make_archive(str(archive_base), "zip", root_dir=mod_dir)
        return Path(archive).read_bytes()
