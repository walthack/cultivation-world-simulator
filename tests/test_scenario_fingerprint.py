from __future__ import annotations

from src.scenario.scenario_fingerprint import compute_scenario_fingerprint


def _scenario() -> dict:
    return {
        "schema_version": "0.1",
        "scenario_id": "sample",
        "title": "Sample",
        "version": "1.0",
        "world_preset": {"preset_id": "default"},
        "initial_state": {"avatars": [], "relationships": [], "sects": []},
    }


def _timeline() -> dict:
    return {"schema_version": "0.1", "events": []}


def test_compute_scenario_fingerprint_returns_deterministic_hash():
    first = compute_scenario_fingerprint(_scenario(), _timeline())
    second = compute_scenario_fingerprint(_scenario(), _timeline())

    assert first == second
    assert first.startswith("sha256:")
    assert len(first) == len("sha256:") + 64


def test_compute_scenario_fingerprint_excludes_self_reference():
    scenario = _scenario()
    expected = compute_scenario_fingerprint(scenario, _timeline())
    scenario["fingerprint"] = "sha256:" + "0" * 64

    assert compute_scenario_fingerprint(scenario, _timeline()) == expected


def test_compute_scenario_fingerprint_changes_when_content_changes():
    scenario = _scenario()
    changed = _scenario()
    changed["title"] = "Changed"

    assert compute_scenario_fingerprint(scenario, _timeline()) != compute_scenario_fingerprint(changed, _timeline())
