"""v1.8 M3 — transition beat persistence + deterministic replay.

A generated transition beat's MECHANICAL effect (relation_delta) lands in scenario
state, which persists; its audit record lands in the transition ledger, which must
also persist; and the cadence cursor persists (M2). Together these give
deterministic replay: a reload restores the post-beat world, and continuing the
simulation neither re-invokes the generator for an already-generated gap month nor
re-applies the beat's effect. No frozen LLM output is replayed — beats are applied
once and their results are what survive.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.classes.core.world import World
from src.classes.environment.map import Map
from src.classes.environment.tile import TileType
from src.scenario.state import ScriptedScenarioState
from src.scenario.state_access import get_relation
from src.sim.load.load_game import load_game
from src.sim.save.save_game import save_game
from src.sim.simulator import Simulator
from src.sim.simulator_engine.phases.scripted_scenario import phase_scripted_scenario_tick
from src.systems.time import Month, Year, create_month_stamp


def _map():
    m = Map(width=10, height=10)
    for x in range(10):
        for y in range(10):
            m.create_tile(x, y, TileType.PLAIN)
    return m


def _timeline():
    return [
        {"id": "a1", "anchor": True, "trigger": {"year": 100, "month": 1, "condition": {"always": {}}}},
        {"id": "a2", "anchor": True, "trigger": {"year": 100, "month": 4, "condition": {"always": {}}}},
    ]


def _apply_one_beat_generator():
    """Applies a single relation_delta beat on its first (gap) call, then nothing."""
    state = {"calls": 0}

    def gen(snapshot):
        state["calls"] += 1
        if state["calls"] > 1:
            return []
        return [{"id": "b1", "narration": "茶肆闲谈。", "command": {"command": "relation_delta", "a": "hero", "b": "merchant", "delta": 4}}]

    gen.state = state  # type: ignore[attr-defined]
    return gen


async def _advance(world, year, month):
    stamp = create_month_stamp(Year(year), Month(month))
    world.month_stamp = stamp
    return await phase_scripted_scenario_tick(world, SimpleNamespace(month_stamp=stamp))


@pytest.mark.asyncio
async def test_ledger_and_beat_effect_survive_reload_without_reapplying(tmp_path):
    world = World.create_with_db(
        map=_map(),
        month_stamp=create_month_stamp(Year(100), Month.JANUARY),
        events_db_path=tmp_path / "events.db",
    )
    world.transition_generator = _apply_one_beat_generator()
    world.scripted_scenario = ScriptedScenarioState(scenario_id="sample", timeline=_timeline())

    await _advance(world, 100, 1)  # anchor a1 fires (not a gap)
    await _advance(world, 100, 2)  # gap → beat applied here

    sc = world.scripted_scenario
    assert get_relation(sc.state, "hero", "merchant") == 4          # effect applied
    assert any(r["beat_id"] == "b1" and r["accepted"] for r in sc.transition_ledger)
    saved_ledger = list(sc.transition_ledger)
    saved_cursor = sc.transition_last_gen_month

    save_path = tmp_path / "save.json"
    ok, _ = save_game(world, Simulator(world), [], save_path)
    assert ok
    world.event_manager.close()

    # ledger is a top-level scenario field, never inside state (var_equals boundary)
    import json
    sc_blob = json.loads(save_path.read_text(encoding="utf-8"))["scripted_scenario"]
    assert sc_blob["transition_ledger"] == saved_ledger
    assert "transition_ledger" not in sc_blob["state"]

    with patch("src.run.load_map.load_cultivation_world_map", return_value=_map()):
        loaded, _, _ = load_game(save_path, active_scenario_id="sample")

    lsc = loaded.scripted_scenario
    assert get_relation(lsc.state, "hero", "merchant") == 4          # effect persisted
    assert lsc.transition_ledger == saved_ledger                     # ledger persisted
    assert lsc.transition_last_gen_month == saved_cursor             # cadence persisted

    # DETERMINISTIC REPLAY: re-running the same gap month on the reloaded world must
    # NOT re-invoke the generator (frozen cache HIT) nor re-apply the relation delta.
    replay_gen = _apply_one_beat_generator()
    loaded.transition_generator = replay_gen
    await _advance(loaded, 100, 2)
    assert replay_gen.state["calls"] == 0                            # not re-invoked
    assert get_relation(lsc.state, "hero", "merchant") == 4          # not doubled


def _accept_and_reject_generator():
    def gen(snapshot):
        return [
            {"id": "ok", "narration": "允许", "command": {"command": "relation_delta", "a": "hero", "b": "merchant", "delta": 4}},
            {"id": "bad", "narration": "拒绝", "command": {"command": "set_flag", "flag": "nope"}},
        ]
    return gen


@pytest.mark.asyncio
async def test_reject_records_and_frozen_cache_are_json_safe_and_survive_reload(tmp_path):
    world = World.create_with_db(
        map=_map(),
        month_stamp=create_month_stamp(Year(100), Month.JANUARY),
        events_db_path=tmp_path / "events.db",
    )
    world.transition_generator = _accept_and_reject_generator()
    world.scripted_scenario = ScriptedScenarioState(scenario_id="sample", timeline=_timeline())

    await _advance(world, 100, 1)
    await _advance(world, 100, 2)  # gap → one accepted, one rejected beat

    sc = world.scripted_scenario
    reject = next(r for r in sc.transition_ledger if not r["accepted"])
    assert "whitelist" in reject["reason"]

    save_path = tmp_path / "save.json"
    ok, _ = save_game(world, Simulator(world), [], save_path)  # would raise if ledger/cache not JSON-safe
    assert ok
    world.event_manager.close()

    with patch("src.run.load_map.load_cultivation_world_map", return_value=_map()):
        loaded, _, _ = load_game(save_path, active_scenario_id="sample")

    lsc = loaded.scripted_scenario
    # the rejection reason and the frozen cache both survive the JSON round-trip
    assert any(not r["accepted"] and "whitelist" in r.get("reason", "") for r in lsc.transition_ledger)
    assert lsc.transition_cache  # frozen gap beats persisted
