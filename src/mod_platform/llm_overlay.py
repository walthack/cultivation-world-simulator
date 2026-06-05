from __future__ import annotations

from pathlib import Path


_PROMPT_OVERLAYS: dict[str, Path] = {}


def configure_llm_overlays(entries: list[tuple[str, Path]]) -> None:
    overlays: dict[str, Path] = {}
    for key, path in entries:
        if key and path.exists():
            overlays[str(key)] = Path(path)
    global _PROMPT_OVERLAYS
    _PROMPT_OVERLAYS = overlays


def resolve_prompt_template(template_path: Path | str) -> Path | None:
    raw = str(template_path)
    path = Path(raw)
    candidates = [raw, path.stem, path.name]
    for candidate in candidates:
        overlay = _PROMPT_OVERLAYS.get(candidate)
        if overlay is not None:
            return overlay
    return None


def get_prompt_overlays() -> dict[str, str]:
    return {key: str(path) for key, path in _PROMPT_OVERLAYS.items()}
