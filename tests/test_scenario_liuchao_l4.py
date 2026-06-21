"""The shipped 六朝 scenario packages exercise the v1.9 L4 stack end-to-end.

Proves the Narrative Director's backbone gates actually engage on REAL authored content
(not just synthetic fixtures). Each per-book package (liuchao=清羽记, yunlongyin=云龙吟)
declares a backbone (prohibited outcomes + a canonical irreversible fact) and mandatory
anchors; the director is rejected when a proposal would reverse the irreversible fact or
trip a prohibited outcome.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.scenario import scenario_loader
from src.scenario.narrative_director import _backbone_reason
from src.scenario.state import ScriptedScenarioState


# (scenario_id, irreversible flag, a prohibited flag, some mandatory anchor ids)
PACKAGES = [
    ("liuchao", "duan_qiang_fallen", "taiyi_destroyed", {"liuchao-opening", "duan-qiang-falls", "book-a-finale-onward"}),
    ("yunlongyin", "lishishi_clan_fallen", "taiyi_destroyed", {"yunlong-arrive-linan", "lishishi-clan-massacre", "book-b-finale-to-han"}),
]


def _world(scenario_id):
    resolved = scenario_loader.load(scenario_id)
    sc = ScriptedScenarioState(scenario_id=scenario_id, timeline=list(resolved.timeline), backbone=resolved.backbone)
    return SimpleNamespace(scripted_scenario=sc), resolved


def _state(flags):
    return {
        "world": SimpleNamespace(world_flags=dict(flags)),
        "relations": {},
        "scripted_scenario_state": {},
        "player": {"id": "cheng-zongyang"},
    }


@pytest.mark.parametrize("scenario_id, irreversible, prohibited, mandatory_ids", PACKAGES)
def test_package_ships_an_l4_backbone_and_mandatory_anchors(scenario_id, irreversible, prohibited, mandatory_ids):
    resolved = scenario_loader.load(scenario_id)
    bb = resolved.backbone
    assert {"world_flag": {"flag": irreversible, "value": True}} in bb["irreversible_facts"]
    assert any(p.get("world_flag", {}).get("flag") == prohibited for p in bb["prohibited_predicates"])
    actual_mandatory = {e["id"] for e in resolved.timeline if e.get("mandatory")}
    assert mandatory_ids <= actual_mandatory


@pytest.mark.parametrize("scenario_id, irreversible, prohibited, mandatory_ids", PACKAGES)
def test_package_backbone_blocks_reversing_the_irreversible_fact(scenario_id, irreversible, prohibited, mandatory_ids):
    world, _ = _world(scenario_id)
    reason = _backbone_reason(world, _state({irreversible: True}), [{"type": "clear_flag", "flag": irreversible}])
    assert reason and "irreversible" in reason


@pytest.mark.parametrize("scenario_id, irreversible, prohibited, mandatory_ids", PACKAGES)
def test_package_backbone_blocks_a_prohibited_outcome(scenario_id, irreversible, prohibited, mandatory_ids):
    world, _ = _world(scenario_id)
    reason = _backbone_reason(world, _state({}), [{"type": "set_flag", "flag": prohibited}])
    assert reason and "prohibited" in reason


@pytest.mark.parametrize("scenario_id, irreversible, prohibited, mandatory_ids", PACKAGES)
def test_package_backbone_allows_a_neutral_director_flag(scenario_id, irreversible, prohibited, mandatory_ids):
    world, _ = _world(scenario_id)
    assert _backbone_reason(world, _state({}), [{"type": "set_flag", "flag": "market_rumor"}]) is None
