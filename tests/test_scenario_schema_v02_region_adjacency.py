from __future__ import annotations

import json
from collections import deque
from pathlib import Path

import pytest

import src.config.presets as presets
from src.config.presets import PresetConfigError, get_preset_region_adjacency, get_preset_region_ids


def _is_connected(region_ids: set[str], edges: list[dict]) -> bool:
    if not region_ids:
        return True
    graph = {region_id: set() for region_id in region_ids}
    for edge in edges:
        a = edge["from_region_id"]
        b = edge["to_region_id"]
        graph[a].add(b)
        graph[b].add(a)
    start = next(iter(region_ids))
    seen = {start}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for neighbor in graph[node]:
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    return seen == region_ids


def test_default_region_adjacency_edges_reference_known_regions():
    region_ids = get_preset_region_ids("default")
    edges = get_preset_region_adjacency("default")

    assert edges
    for edge in edges:
        assert edge["from_region_id"] in region_ids
        assert edge["to_region_id"] in region_ids


def test_liuchao_region_adjacency_is_connected():
    region_ids = get_preset_region_ids("liuchao")
    edges = get_preset_region_adjacency("liuchao")

    assert _is_connected(region_ids, edges)


def test_default_region_adjacency_connectivity_sanity():
    edge_region_ids = {
        region_id
        for edge in get_preset_region_adjacency("default")
        for region_id in (edge["from_region_id"], edge["to_region_id"])
    }

    assert _is_connected(edge_region_ids, get_preset_region_adjacency("default"))


def test_region_adjacency_rejects_unknown_region(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    preset = tmp_path / "presets" / "bad"
    preset.mkdir(parents=True)
    (preset / "dynasties.json").write_text(json.dumps({"preset_id": "bad", "dynasties": []}), encoding="utf-8")
    (preset / "regions.json").write_text(
        json.dumps(
            {
                "preset_id": "bad",
                "regions": [
                    {
                        "id": "known",
                        "name": "Known",
                        "type": "normal",
                        "description": "",
                        "dynasty_id": None,
                        "climate": "",
                        "economic_focus": "",
                        "key_landmarks": [],
                        "tags": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (preset / "region_adjacency.json").write_text(
        json.dumps(
            {
                "preset_id": "bad",
                "edges": [
                    {
                        "from_region_id": "known",
                        "to_region_id": "missing",
                        "relation": "neutral",
                        "difficulty": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(presets, "get_presets_root", lambda: tmp_path / "presets")

    with pytest.raises(PresetConfigError, match="unknown to_region_id"):
        get_preset_region_adjacency("bad")


def test_region_adjacency_rejects_invalid_relation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    preset = tmp_path / "presets" / "bad"
    preset.mkdir(parents=True)
    (preset / "dynasties.json").write_text(json.dumps({"preset_id": "bad", "dynasties": []}), encoding="utf-8")
    (preset / "regions.json").write_text(
        json.dumps(
            {
                "preset_id": "bad",
                "regions": [
                    {
                        "id": "a",
                        "name": "A",
                        "type": "normal",
                        "description": "",
                        "dynasty_id": None,
                        "climate": "",
                        "economic_focus": "",
                        "key_landmarks": [],
                        "tags": [],
                    },
                    {
                        "id": "b",
                        "name": "B",
                        "type": "normal",
                        "description": "",
                        "dynasty_id": None,
                        "climate": "",
                        "economic_focus": "",
                        "key_landmarks": [],
                        "tags": [],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (preset / "region_adjacency.json").write_text(
        json.dumps(
            {
                "preset_id": "bad",
                "edges": [{"from_region_id": "a", "to_region_id": "b", "relation": "blocked", "difficulty": 1}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(presets, "get_presets_root", lambda: tmp_path / "presets")

    with pytest.raises(PresetConfigError, match="invalid relation"):
        get_preset_region_adjacency("bad")
