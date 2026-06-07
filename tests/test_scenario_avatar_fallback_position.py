from __future__ import annotations

from pathlib import Path

import pytest

from src.classes.core.world import World
from src.classes.environment.map import Map
from src.classes.environment.region import CityRegion
from src.classes.environment.tile import TileType
from src.config import reset_data_paths_cache, reset_settings_service_cache
from src.run.data_loader import reload_all_static_data
from src.sim.avatar_init import create_scenario_avatar
from src.systems.time import Month, Year, create_month_stamp


@pytest.fixture(autouse=True)
def scenario_position_test_data_root(monkeypatch, isolate_settings_data_root):
    data_root = Path("/private/tmp/claude-501/cws-data")
    data_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CWS_DATA_DIR", str(data_root))
    reset_settings_service_cache()
    reset_data_paths_cache()

    yield

    reset_settings_service_cache()
    reset_data_paths_cache()


@pytest.fixture(scope="module", autouse=True)
def load_static_data_once():
    reload_all_static_data()


def _world(width: int = 10, height: int = 10) -> World:
    game_map = Map(width=width, height=height)
    city_region = CityRegion(
        id=101,
        name="Test City",
        desc="Test city region",
        cors=[(0, 0)],
    )
    game_map.regions[city_region.id] = city_region
    for x in range(width):
        for y in range(height):
            game_map.create_tile(x, y, TileType.PLAIN)
    return World(map=game_map, month_stamp=create_month_stamp(Year(1), Month.JANUARY))


def _scenario_avatar(avatar_id: str = "scenario-avatar") -> dict:
    return {
        "id": avatar_id,
        "surname": "测",
        "given_name": "试",
        "gender": "男",
        "age": 28,
        "sect_id": None,
        "realm": "QI_REFINEMENT",
        "stage": "EARLY_STAGE",
        "level": 1,
        "persona_traits": [],
        "goldfinger_id": "CHILD_OF_FORTUNE",
    }


@pytest.mark.asyncio
async def test_scenario_avatar_gets_random_position_and_tile(mock_llm_managers):
    world = _world()

    avatar = create_scenario_avatar(
        world,
        _scenario_avatar(),
        world.month_stamp,
        preset_id="default",
    )

    assert 0 <= avatar.pos_x < world.map.width
    assert 0 <= avatar.pos_y < world.map.height
    assert avatar.tile is world.map.get_tile(avatar.pos_x, avatar.pos_y)
    assert avatar.born_region_id != -1


@pytest.mark.asyncio
async def test_scenario_avatars_scatter_across_runs(mock_llm_managers):
    observed_positions = set()

    for trial in range(30):
        world = _world()
        avatar = create_scenario_avatar(
            world,
            _scenario_avatar(f"scenario-avatar-{trial}"),
            world.month_stamp,
            preset_id="default",
        )
        observed_positions.add((avatar.pos_x, avatar.pos_y))

    assert len(observed_positions) > 1


@pytest.mark.asyncio
async def test_scenario_avatar_creation_uses_map_bounds(mock_llm_managers):
    width = 20
    height = 20

    for trial in range(50):
        world = _world(width=width, height=height)
        avatar = create_scenario_avatar(
            world,
            _scenario_avatar(f"bounded-scenario-avatar-{trial}"),
            world.month_stamp,
            preset_id="default",
        )

        assert 0 <= avatar.pos_x < width
        assert 0 <= avatar.pos_y < height
