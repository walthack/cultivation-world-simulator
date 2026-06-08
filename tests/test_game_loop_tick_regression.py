from __future__ import annotations

import copy
import logging
from pathlib import Path

import pytest

from src.classes.core.world import World
from src.classes.environment.map import Map
from src.classes.environment.tile import TileType
from src.scenario.effect_applier import EffectError, apply_effects, register_effect, spawn_npc, unregister_effect
from src.scenario.injector import inject_scenario_into_world
from src.scenario.scenario_loader import ResolvedScenario
from src.sim.simulator import Simulator
from src.systems.time import Month, Year, create_month_stamp


class _NonPicklableWorld:
    def __init__(self):
        self.world_flags = {}

    def __getstate__(self):
        raise TypeError("cannot pickle 'sqlite3.Connection' object")


def _world(tmp_path: Path) -> World:
    game_map = Map(width=4, height=4)
    for x in range(4):
        for y in range(4):
            game_map.create_tile(x, y, TileType.PLAIN)
    return World.create_with_db(
        map=game_map,
        month_stamp=create_month_stamp(Year(1), Month.JANUARY),
        events_db_path=tmp_path / "events.db",
    )


def _liuchao_scenario() -> ResolvedScenario:
    scenario = {
        "schema_version": "1.2",
        "scenario_id": "liuchao",
        "title": "Liuchao Regression Fixture",
        "version": "1.0",
        "world_preset": {"preset_id": "liuchao"},
        "initial_state": {
            "year": 1,
            "month": 1,
            "avatars": [
                {
                    "id": "wang-zhe",
                    "surname": "王",
                    "given_name": "哲",
                    "gender": "男",
                    "age": 80,
                    "realm": "YUAN_YING",
                    "stage": "LATE_STAGE",
                    "level": 90,
                    "backstory": "regression fixture",
                    "persona_traits": [],
                    "goldfinger_id": None,
                    "long_term_objective": "",
                }
            ],
            "sects": [],
            "relationships": [],
            "world_flags": {"liuchao_started": True},
        },
    }
    timeline = [
        {
            "id": "liuchao-opening",
            "type": "side_event",
            "trigger": {"year": 1, "month": 1, "condition": {"always": {}}},
            "name": "六朝开局",
            "description": "程宗扬踏入六朝局中。",
            "effects": [{"type": "set_flag", "flag": "liuchao_opening_seen"}],
        }
    ]
    return ResolvedScenario(
        scenario_id="liuchao",
        title="Liuchao Regression Fixture",
        version="1.0",
        preset_id="liuchao",
        scenario=scenario,
        timeline=timeline,
    )


def _scenario_world(tmp_path: Path) -> World:
    world = _world(tmp_path)
    inject_scenario_into_world(world, _liuchao_scenario())
    return world


def test_scripted_scenario_apply_effects_does_not_pickle_world():
    state = {
        "npcs": {},
        "relations": {},
        "world_flags": {},
        "world": _NonPicklableWorld(),
        "scenario_runtime": {"triggered_event_ids": []},
        "scripted_scenario_state": {},
    }

    unregister_effect("spawn_npc")
    register_effect("spawn_npc", spawn_npc, source="test")
    try:
        apply_effects(state, [{"type": "spawn_npc", "id": "test-1", "name": "测试一"}])
    finally:
        unregister_effect("spawn_npc")

    assert state["npcs"]["test-1"]["name"] == "测试一"


@pytest.mark.asyncio
async def test_sim_step_advances_month_with_scripted_scenario(tmp_path: Path, mock_llm_managers):
    world = _scenario_world(tmp_path)
    initial_month_stamp = world.month_stamp
    sim = Simulator(world)

    for _ in range(3):
        await sim.step()

    assert int(world.month_stamp) == int(initial_month_stamp) + 3


@pytest.mark.asyncio
async def test_game_loop_logs_no_pickle_error(tmp_path: Path, mock_llm_managers, caplog: pytest.LogCaptureFixture):
    world = _scenario_world(tmp_path)
    sim = Simulator(world)

    with caplog.at_level(logging.WARNING):
        for _ in range(3):
            await sim.step()

    messages = [record.getMessage() for record in caplog.records]
    assert not any("cannot pickle" in message or "sqlite3.Connection" in message for message in messages)


def test_apply_effects_rolls_back_state_on_handler_error():
    state = {
        "npcs": {
            "before": {"id": "before", "name": "原始", "skills": [], "stats": {}, "items": [], "alive": True}
        },
        "relations": {"a:b": 1},
        "world_flags": {"before": True},
        "triggered_event_ids": ["before"],
        "blocked_event_ids": ["blocked-before"],
        "event_outcomes": {"before": {"choice_id": "old"}},
        "scenario_runtime": {"triggered_event_ids": ["runtime-before"]},
        "scripted_scenario_state": {"phase": "before"},
        "player": {"skills": [], "stats": {}, "items": []},
    }
    before = copy.deepcopy(
        {
            key: state[key]
            for key in (
                "npcs",
                "relations",
                "world_flags",
                "triggered_event_ids",
                "blocked_event_ids",
                "event_outcomes",
                "scenario_runtime",
                "scripted_scenario_state",
            )
        }
    )

    unregister_effect("spawn_npc")
    register_effect("spawn_npc", spawn_npc, source="test")
    try:
        with pytest.raises(EffectError, match="effect must be an object"):
            apply_effects(
                state,
                [
                    {"type": "spawn_npc", "id": "after", "name": "之后"},
                    {"type": "npc_set_relation", "a": "before", "b": "after", "value": 99},
                    {"type": "set_flag", "flag": "after_flag"},
                    {"type": "world_event_trigger", "event_id": "after-event"},
                    {"type": "set_var", "name": "phase", "value": "after"},
                    {"type": "gain_skill", "skill": "after-skill"},
                    "bad-effect",
                ],
            )
    finally:
        unregister_effect("spawn_npc")

    assert {key: state[key] for key in before} == before
