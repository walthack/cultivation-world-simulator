from __future__ import annotations

import os

import pytest

os.environ.setdefault("CWS_DATA_DIR", "/private/tmp/cws-sanguo-test-data")

from src.classes.core.world import World
from src.classes.environment.map import Map
from src.classes.environment.tile import TileType
from src.scenario.injector import inject_scenario_into_world
from src.scenario.scenario_loader import load
from src.sim.simulator import Simulator
from src.systems.time import Month, Year, create_month_stamp


def _world_at(year: int, month: Month) -> World:
    game_map = Map(width=4, height=4)
    for x in range(4):
        for y in range(4):
            game_map.create_tile(x, y, TileType.PLAIN)
    return World(map=game_map, month_stamp=create_month_stamp(Year(year), month))


def _scenario_world_at(year: int, month: Month, *, controlled_avatar: str | None = None) -> World:
    world = _world_at(year, month)
    inject_scenario_into_world(world, load("sanguo"))
    if controlled_avatar is not None:
        world.scripted_scenario.state["controlled_avatar"] = controlled_avatar
    return world


def test_sanguo_loads():
    scenario = load("sanguo")

    avatars = scenario.scenario["initial_state"]["avatars"]
    avatar_ids = {avatar["id"] for avatar in avatars}

    assert scenario.scenario_id == "sanguo"
    assert scenario.preset_id == "sanguo"
    assert len(avatars) == 3
    assert {"liu-bei", "cao-cao", "sun-quan"} <= avatar_ids


@pytest.mark.asyncio
async def test_sanguo_phase_dispatches_main_event():
    world = _scenario_world_at(208, Month.JANUARY)

    events = await Simulator(world).step()
    ids = [event.id for event in events]

    assert "shu-hanzhong-supply" in ids
    assert "shu-hanzhong-supply" in world.scripted_scenario.triggered_events
    assert world.world_flags["shu_hanzhong_supply_ready"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("controlled_avatar", "expected_event_id"),
    [
        ("liu-bei", "liu-bei-arrives-at-chibi-eve"),
        ("cao-cao", "cao-cao-arrives-at-chibi-eve"),
        ("sun-quan", "sun-quan-arrives-at-chibi-eve"),
    ],
)
async def test_sanguo_perspective_filtering(controlled_avatar, expected_event_id):
    world = _scenario_world_at(208, Month.OCTOBER, controlled_avatar=controlled_avatar)

    events = await Simulator(world).step()
    ids = [event.id for event in events]

    assert expected_event_id in ids
    assert [event_id for event_id in ids if event_id.endswith("-arrives-at-chibi-eve")] == [expected_event_id]
    assert world.world_flags[f"sanguo_chibi_eve_witnessed_by_{controlled_avatar}"] is True


@pytest.mark.asyncio
async def test_sanguo_controlled_avatar_placeholder():
    world = _scenario_world_at(208, Month.OCTOBER, controlled_avatar="liu-bei")

    events = await Simulator(world).step()
    ids = [event.id for event in events]
    flags = world.world_flags

    assert "liu-bei-arrives-at-chibi-eve" in ids
    assert flags["sanguo_chibi_eve_witnessed_by_liu-bei"] is True
    assert "sanguo_chibi_eve_witnessed_by_{controlled_avatar}" not in flags
