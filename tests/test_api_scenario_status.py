from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.classes.age import Age
from src.classes.alignment import Alignment
from src.classes.core.avatar import Avatar, Gender
from src.classes.core.world import World
from src.classes.environment.map import Map
from src.classes.environment.tile import TileType
from src.classes.root import Root
from src.scenario.injector import inject_scenario_into_world
from src.scenario.scenario_loader import load
from src.server.api.public_v1.query import create_public_query_router
from src.server.assemblers.scenario_status import build_scenario_status
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


def _scenario_world() -> tuple[World, object]:
    world = _world()
    _avatar(world, "cheng-zongyang", "程宗扬")
    _avatar(world, "wang-zhe", "王哲")
    _avatar(world, "xiao-zi", "小紫")
    scenario = load("liuchao")
    inject_scenario_into_world(world, scenario)
    return world, scenario


def _client_for_status(builder):
    app = FastAPI()
    noop = lambda: {}
    app.include_router(
        create_public_query_router(
            build_runtime_status=noop,
            build_world_state=noop,
            build_world_map=noop,
            build_current_run=noop,
            build_events_page=lambda **_kwargs: {},
            build_rankings=noop,
            build_sect_relations=noop,
            build_game_data=noop,
            build_avatar_adjust_options=noop,
            build_avatar_meta=noop,
            build_avatar_list=noop,
            build_phenomena=noop,
            build_sect_territories=noop,
            build_mortal_overview=noop,
            build_dynasty_overview=noop,
            build_dynasty_detail=noop,
            build_scenario_status=builder,
            build_avatar_overview=noop,
            build_saves=noop,
            build_detail=lambda **_kwargs: {},
            build_deceased_list=noop,
            build_roleplay_session=noop,
        )
    )
    return TestClient(app)


def test_active_scenario_status_starts_untriggered():
    world, scenario = _scenario_world()
    client = _client_for_status(lambda: build_scenario_status(world, scenario))

    response = client.get("/api/v1/query/scenario/status")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["active"] is True
    assert data["scenario_id"] == "liuchao"
    assert data["timeline"]["total_events"] > 0
    assert data["timeline"]["triggered_count"] == 0


@pytest.mark.asyncio
async def test_scenario_status_after_liuchao_opening_step(mock_llm_managers):
    world, scenario = _scenario_world()

    await Simulator(world).step()
    client = _client_for_status(lambda: build_scenario_status(world, scenario))
    response = client.get("/api/v1/query/scenario/status")

    data = response.json()["data"]
    events_by_id = {event["id"]: event for event in data["timeline"]["events"]}
    assert data["timeline"]["triggered_count"] == 1
    assert events_by_id["liuchao-opening"]["triggered"] is True


def test_no_scenario_status_returns_inactive():
    world = _world()
    client = _client_for_status(lambda: build_scenario_status(world, None))

    response = client.get("/api/v1/query/scenario/status")

    assert response.status_code == 200
    assert response.json()["data"] == {"active": False}
