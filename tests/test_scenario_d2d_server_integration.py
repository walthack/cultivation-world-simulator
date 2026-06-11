from __future__ import annotations

import subprocess
import sys
import os
from pathlib import Path

import pytest

os.environ.setdefault("CWS_DATA_DIR", "/private/tmp/cws-d2d-test-data")

from src.classes.age import Age
from src.classes.alignment import Alignment
from src.classes.core.avatar import Avatar, Gender
from src.classes.core.world import World
from src.classes.environment.map import Map
from src.classes.environment.tile import TileType
from src.classes.root import Root
from src.scenario.injector import inject_scenario_into_world
from src.scenario.event_dispatcher import EventDispatcher
from src.scenario.scenario_loader import load
from src.scenario.state import ScriptedScenarioState
from src.server.runtime import GameSessionRuntime, create_default_game_state
from src.server.services.roleplay_service import start_roleplay
from src.sim.simulator import Simulator
from src.systems.cultivation import Realm
from src.systems.time import Month, Year, create_month_stamp


def _world() -> World:
    game_map = Map(width=4, height=4)
    for x in range(4):
        for y in range(4):
            game_map.create_tile(x, y, TileType.PLAIN)
    return World(map=game_map, month_stamp=create_month_stamp(Year(1), Month.JANUARY))


def _avatar(world: World, avatar_id: str, name: str) -> Avatar:
    avatar = Avatar(
        world=world,
        name=name,
        id=avatar_id,
        birth_month_stamp=create_month_stamp(Year(1), Month.JANUARY),
        age=Age(28, Realm.Qi_Refinement, innate_max_lifespan=80),
        gender=Gender.MALE,
        root=Root.WOOD,
        personas=[],
        alignment=Alignment.NEUTRAL,
    )
    avatar.technique = None
    avatar.recalc_effects()
    world.avatar_manager.register_avatar(avatar)
    return avatar


def _scenario_world(*, controlled_avatar: str | None = None) -> World:
    world = _world()
    _avatar(world, "cheng-zongyang", "程宗扬")
    _avatar(world, "wang-zhe", "王哲")
    _avatar(world, "xiao-zi", "小紫")
    inject_scenario_into_world(world, load("liuchao"))
    if controlled_avatar is not None:
        runtime = GameSessionRuntime(create_default_game_state())
        runtime.update({"world": world})
        world.runtime = runtime
        start_roleplay(runtime, avatar_id=controlled_avatar)
    return world


@pytest.mark.asyncio
async def test_no_scenario_boot_defaults_to_none_and_phase_noops(mock_llm_managers):
    world = _world()

    assert world.scripted_scenario is None

    events = await Simulator(world).step()

    assert world.scripted_scenario is None
    assert [event for event in events if event.event_type == "scenario"] == []


def test_scenario_flag_injection_sets_world_scripted_scenario():
    world = _world()
    inject_scenario_into_world(world, load("liuchao"))

    assert isinstance(world.scripted_scenario, ScriptedScenarioState)
    assert world.scripted_scenario.scenario_id == "liuchao"
    assert world.scripted_scenario.timeline


@pytest.mark.asyncio
async def test_liuchao_opening_fires_on_year_1_month_1(mock_llm_managers):
    world = _scenario_world()

    events = await Simulator(world).step()

    assert "liuchao-opening" in [event.id for event in events]
    assert "liuchao-opening" in world.scripted_scenario.triggered_events


@pytest.mark.asyncio
async def test_server_scenario_world_uses_initial_state_start_time_without_manual_pin(
    mock_llm_managers,
    monkeypatch,
    tmp_path,
):
    from src.server import main as server_main

    game_map = Map(width=4, height=4)
    for x in range(4):
        for y in range(4):
            game_map.create_tile(x, y, TileType.PLAIN)

    monkeypatch.setattr(server_main, "ACTIVE_SCENARIO", load("liuchao"))
    world = server_main.ScenarioInjectedWorld.create_with_db(
        map=game_map,
        month_stamp=create_month_stamp(Year(100), Month.JANUARY),
        events_db_path=tmp_path / "events.db",
        start_year=100,
    )

    month_stamp = world.month_stamp
    dispatched = await EventDispatcher(world.scripted_scenario.timeline).dispatch_month(
        {"world": world, "scenario_runtime": {"triggered_event_ids": []}},
        year=int(month_stamp.get_year()),
        month=int(month_stamp.get_month().value),
    )

    assert int(world.month_stamp.get_year()) == 1
    assert int(world.month_stamp.get_month().value) == 1
    assert "liuchao-opening" in [event["id"] for event in dispatched]


@pytest.mark.asyncio
async def test_cheng_zongyang_perspective_receives_month_2_origin_event(mock_llm_managers):
    world = _scenario_world(controlled_avatar="cheng-zongyang")
    sim = Simulator(world)

    await sim.step()
    events = await sim.step()

    ids = [event.id for event in events]
    assert ids == ["duan-qiang-falls"]


@pytest.mark.asyncio
async def test_wang_zhe_roleplay_bridge_keeps_controlled_avatar_for_origin_event(mock_llm_managers):
    world = _scenario_world(controlled_avatar="wang-zhe")
    sim = Simulator(world)

    await sim.step()
    events = await sim.step()

    ids = [event.id for event in events]
    assert world.scripted_scenario.state["controlled_avatar"] == "wang-zhe"
    assert ids == ["duan-qiang-falls"]


def test_unknown_scenario_id_fails_before_server_boot():
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "sys.argv=['src/server/main.py','--dev','--scenario','does-not-exist']; "
                "import src.server.main"
            ),
        ],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=20,
    )

    assert result.returncode != 0
    assert "does-not-exist" in result.stderr
