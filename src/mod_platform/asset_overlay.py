from __future__ import annotations

from pathlib import Path


_OVERLAY_DIRS: list[Path] = []
_BUNDLED_ASSETS_ROOT: Path | None = None


def configure_asset_overlay(mod_asset_dirs: list[Path], bundled_assets_root: Path | str | None = None) -> None:
    global _OVERLAY_DIRS, _BUNDLED_ASSETS_ROOT
    _OVERLAY_DIRS = [Path(item) for item in mod_asset_dirs if Path(item).is_dir()]
    if bundled_assets_root is not None:
        _BUNDLED_ASSETS_ROOT = Path(bundled_assets_root)


def get_overlay_dirs() -> list[Path]:
    return list(_OVERLAY_DIRS)


def resolve_asset(path: str | Path, bundled_assets_root: Path | str | None = None) -> Path:
    relative = Path(str(path).lstrip("/"))
    if relative.parts and relative.parts[0] == "assets":
        relative = Path(*relative.parts[1:])

    for overlay_dir in reversed(_OVERLAY_DIRS):
        candidate = overlay_dir / relative
        if candidate.exists():
            return candidate

    root = Path(bundled_assets_root) if bundled_assets_root is not None else _BUNDLED_ASSETS_ROOT
    if root is None:
        return relative
    return root / relative
