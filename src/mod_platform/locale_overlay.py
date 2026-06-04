from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.i18n.locale_registry import normalize_locale_code


_LOCALE_STRINGS: dict[str, dict[str, str]] = {}
_LOCALE_SOURCES: dict[tuple[str, str], str] = {}


def configure_locale_overlays(entries: list[tuple[str, Path, str]]) -> list[dict[str, Any]]:
    strings: dict[str, dict[str, str]] = {}
    sources: dict[tuple[str, str], str] = {}
    conflicts: list[dict[str, Any]] = []

    for locale_code, path, mod_id in entries:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            continue
        normalized_locale = normalize_locale_code(locale_code)
        bucket = strings.setdefault(normalized_locale, {})
        for key, value in payload.items():
            source_key = (normalized_locale, str(key))
            previous_mod = sources.get(source_key)
            if previous_mod and previous_mod != mod_id:
                conflicts.append({"locale": normalized_locale, "key": str(key), "mod_ids": [previous_mod, mod_id]})
            bucket[str(key)] = str(value)
            sources[source_key] = mod_id

    global _LOCALE_STRINGS, _LOCALE_SOURCES
    _LOCALE_STRINGS = strings
    _LOCALE_SOURCES = sources
    return conflicts


def translate(locale_code: str, key: str) -> str | None:
    normalized = normalize_locale_code(locale_code)
    return _LOCALE_STRINGS.get(normalized, {}).get(key)


def get_locale_overlays() -> dict[str, dict[str, str]]:
    return {locale: dict(values) for locale, values in _LOCALE_STRINGS.items()}
