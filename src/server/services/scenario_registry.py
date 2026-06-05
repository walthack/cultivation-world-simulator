from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.scenario.scenario_loader import get_project_root

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class InstalledScenarioMeta:
    id: str
    name: str
    version: str
    author: str | None = None
    description: str = ""
    tags: list[str] = field(default_factory=list)
    cover_image: str | None = None

    def model_dump(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "tags": list(self.tags),
            "cover_image": self.cover_image,
        }


def _metadata_from_file(path: Path) -> InstalledScenarioMeta | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Skipping scenario directory %s: invalid scenario.json: %s", path.parent, exc)
        return None

    if not isinstance(raw, dict):
        logger.warning("Skipping scenario directory %s: scenario.json is not an object", path.parent)
        return None

    scenario_id = raw.get("scenario_id")
    title = raw.get("title")
    version = raw.get("version")
    description = raw.get("description")
    if not all(isinstance(value, str) and value.strip() for value in (scenario_id, title, version, description)):
        logger.warning("Skipping scenario directory %s: missing required metadata", path.parent)
        return None

    tags = raw.get("tags", [])
    if not isinstance(tags, list):
        tags = []
    tags = [str(item) for item in tags if isinstance(item, str) and item.strip()]

    author = raw.get("author")
    cover_image = raw.get("cover_image")

    return InstalledScenarioMeta(
        id=scenario_id,
        name=title,
        version=version,
        author=author if isinstance(author, str) and author.strip() else None,
        description=description,
        tags=tags,
        cover_image=cover_image if isinstance(cover_image, str) and cover_image.strip() else None,
    )


def list_installed_scenarios(*, scenarios_root: Path | None = None) -> list[InstalledScenarioMeta]:
    root = scenarios_root or (get_project_root() / "config" / "scenarios")
    if not root.is_dir():
        return []

    scenarios: list[InstalledScenarioMeta] = []
    for scenario_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        meta = _metadata_from_file(scenario_dir / "scenario.json")
        if meta is not None:
            scenarios.append(meta)
    return scenarios
