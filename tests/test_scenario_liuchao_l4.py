"""The shipped liuchao package exercises the v1.9 L4 stack end-to-end.

Proves the Narrative Director's backbone gates actually engage on REAL authored
content (not just synthetic fixtures): liuchao declares a backbone (prohibited
outcomes + the canonical irreversible death of 段强) and mandatory anchors, and the
director is rejected when a proposal would resurrect 段强 or trip a prohibited outcome.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.scenario import scenario_loader
from src.scenario.narrative_director import _backbone_reason
from src.scenario.state import ScriptedScenarioState


def _world():
    resolved = scenario_loader.load("liuchao")
    sc = ScriptedScenarioState(scenario_id="liuchao", timeline=list(resolved.timeline), backbone=resolved.backbone)
    return SimpleNamespace(scripted_scenario=sc), resolved


def _state(flags):
    return {
        "world": SimpleNamespace(world_flags=dict(flags)),
        "relations": {},
        "scripted_scenario_state": {},
        "player": {"id": "cheng-zongyang"},
    }


def test_liuchao_ships_an_l4_backbone_and_mandatory_anchors():
    resolved = scenario_loader.load("liuchao")
    bb = resolved.backbone
    assert {"world_flag": {"flag": "duan_qiang_fallen", "value": True}} in bb["irreversible_facts"]
    assert any(p.get("world_flag", {}).get("flag") == "taiyi_destroyed" for p in bb["prohibited_predicates"])
    mandatory = [e["id"] for e in resolved.timeline if e.get("mandatory")]
    assert {"liuchao-opening", "duan-qiang-falls", "book-a-finale-onward"} <= set(mandatory)


def test_liuchao_backbone_blocks_resurrecting_duan_qiang():
    world, _ = _world()
    # 段强之死 is canonical + irreversible; clearing the death flag = resurrection.
    reason = _backbone_reason(world, _state({"duan_qiang_fallen": True}), [{"type": "clear_flag", "flag": "duan_qiang_fallen"}])
    assert reason and "irreversible" in reason


def test_liuchao_backbone_blocks_a_prohibited_outcome():
    world, _ = _world()
    reason = _backbone_reason(world, _state({}), [{"type": "set_flag", "flag": "taiyi_destroyed"}])
    assert reason and "prohibited" in reason


def test_liuchao_backbone_allows_a_neutral_director_flag():
    world, _ = _world()
    assert _backbone_reason(world, _state({}), [{"type": "set_flag", "flag": "market_rumor"}]) is None
