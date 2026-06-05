from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.config.data_paths import get_data_paths
from src.scenario.scenario_loader import get_project_root
from src.server.services import scenario_state

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
    source: str = "bundled"
    enabled: bool = True

    def model_dump(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "tags": list(self.tags),
            "cover_image": self.cover_image,
            "source": self.source,
            "enabled": self.enabled,
        }


def _metadata_from_file(path: Path, *, source: str, enabled: bool) -> InstalledScenarioMeta | None:
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
    if not all(isinstance(value, str) and value.strip() for value in (scenario_id, title, version)):
        logger.warning("Skipping scenario directory %s: missing required metadata", path.parent)
        return None
    description = raw.get("description", "")
    if not isinstance(description, str):
        description = ""

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
        source=source,
        enabled=enabled,
    )


def _scan_root(root: Path, *, source: str, state: dict[str, dict[str, bool]]) -> list[InstalledScenarioMeta]:
    if not root.is_dir():
        return []

    scenarios: list[InstalledScenarioMeta] = []
    for scenario_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        scenario_id = scenario_dir.name
        enabled = bool(state.get(scenario_id, {}).get("enabled", True))
        meta = _metadata_from_file(scenario_dir / "scenario.json", source=source, enabled=enabled)
        if meta is not None:
            scenarios.append(meta)
    return scenarios


def list_installed_scenarios(*, scenarios_root: Path | None = None) -> list[InstalledScenarioMeta]:
    state = scenario_state.get_state()
    if scenarios_root is not None:
        return _scan_root(scenarios_root, source="bundled", state=state)

    bundled_root = get_project_root() / "config" / "scenarios"
    installed_root = get_data_paths().root / "scenarios"
    bundled = _scan_root(bundled_root, source="bundled", state=state)
    bundled_ids = {scenario.id for scenario in bundled}
    installed = [
        scenario
        for scenario in _scan_root(installed_root, source="installed", state=state)
        if scenario.id not in bundled_ids
    ]
    return bundled + installed
