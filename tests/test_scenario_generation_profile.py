from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.classes.core.world import World
from src.classes.environment.map import Map
from src.classes.environment.region import CityRegion
from src.classes.environment.tile import TileType
from src.run.data_loader import reload_all_static_data
from src.scenario.injector import inject_scenario_initial_state_into_world
from src.scenario.scenario_loader import ScenarioValidationError, load
from src.server.init_flow import (
    _generate_initial_avatars,
    _select_scenario_existed_sects,
    resolve_generation_counts,
)
from src.sim.avatar_init import create_scenario_avatar
from src.systems.time import Month, Year, create_month_stamp


@pytest.fixture(scope="module", autouse=True)
def load_static_data_once():
    reload_all_static_data()


class _Sect:
    def __init__(self, sect_id: int):
        self.id = sect_id


def _settings(init_npc_num: int = 9, sect_num: int = 3):
    return SimpleNamespace(init_npc_num=init_npc_num, sect_num=sect_num)


def _scenario(profile: dict | None = None, *, avatars: list[dict] | None = None, sects: list[dict] | None = None):
    initial_state = {
        "year": 1,
        "month": 1,
        "avatars": avatars if avatars is not None else [_scenario_avatar()],
        "sects": sects if sects is not None else [],
        "relationships": [],
        "world_flags": {},
    }
    if profile is not None:
        initial_state["generation_profile"] = profile
    return SimpleNamespace(
        scenario_id="profile_fixture",
        preset_id="default",
        scenario={
            "schema_version": "1.1",
            "scenario_id": "profile_fixture",
            "title": "Profile Fixture",
            "version": "1.0",
            "world_preset": {"preset_id": "default"},
            "initial_state": initial_state,
        },
        timeline=[],
    )


def _scenario_avatar(avatar_id: str = "scripted-avatar", **patch) -> dict:
    avatar = {
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
    avatar.update(patch)
    return avatar


def _world(width: int = 10, height: int = 10) -> World:
    game_map = Map(width=width, height=height)
    for x in range(width):
        for y in range(height):
            game_map.create_tile(x, y, TileType.PLAIN)

    city_region = CityRegion(
        id=101,
        name="Test City",
        desc="Test city region",
        cors=[(1, 1), (1, 2), (2, 1), (2, 2)],
    )
    game_map.regions[city_region.id] = city_region
    game_map.region_cors[city_region.id] = list(city_region.cors)
    for x, y in city_region.cors:
        game_map.get_tile(x, y).region = city_region

    return World(map=game_map, month_stamp=create_month_stamp(Year(1), Month.JANUARY))


async def _spawn_random_and_scripted(world: World, scenario, *, random_npc_count: int) -> None:
    random_avatars = await _generate_initial_avatars(
        world=world,
        target_total_count=random_npc_count,
        existed_sects=[],
        make_random_avatars=lambda w, count, current_month_stamp, existed_sects: {
            f"random-{idx}": SimpleNamespace(id=f"random-{idx}")
            for idx in range(count)
        },
    )
    world.avatar_manager.avatars.update(random_avatars)
    inject_scenario_initial_state_into_world(world, scenario)


def _write_scenario(tmp_path: Path, *, scenario_patch: dict | None = None, avatar_patch: dict | None = None) -> Path:
    root = tmp_path / "scenarios"
    scenario_dir = root / "profile_fixture"
    scenario_dir.mkdir(parents=True)
    scenario = {
        "schema_version": "1.1",
        "scenario_id": "profile_fixture",
        "title": "Profile Fixture",
        "version": "1.0",
        "world_preset": {"preset_id": "default"},
        "initial_state": {
            "year": 1,
            "month": 1,
            "avatars": [_scenario_avatar(**(avatar_patch or {}))],
            "sects": [],
            "relationships": [],
            "world_flags": {},
        },
    }
    if scenario_patch:
        scenario.update(scenario_patch)
    timeline = {"schema_version": "0.1", "events": []}
    (scenario_dir / "scenario.json").write_text(json.dumps(scenario, ensure_ascii=False), encoding="utf-8")
    (scenario_dir / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False), encoding="utf-8")
    return root


@pytest.mark.asyncio
async def test_profile_random_npc_count_overrides_default(mock_llm_managers):
    scenario = _scenario({"random_npc_count": 2})
    counts = resolve_generation_counts(scenario=scenario, settings=_settings(init_npc_num=9))
    world = _world()

    await _spawn_random_and_scripted(world, scenario, random_npc_count=counts["npc_count"])

    assert len(world.avatar_manager.avatars) == 3
    assert "scripted-avatar" in world.avatar_manager.avatars


def test_profile_random_sect_count_overrides_default():
    scenario = _scenario(
        {"random_sect_count": 2},
        sects=[{"id": 1, "leader_avatar_id": None, "member_avatar_ids": []}],
    )
    counts = resolve_generation_counts(scenario=scenario, settings=_settings(sect_num=9))
    selected = _select_scenario_existed_sects(
        sects_by_id={idx: _Sect(idx) for idx in range(1, 6)},
        random_sect_count=counts["sect_count"],
        resolved_scenario=scenario,
    )

    assert len(selected) == 3
    assert selected[0].id == 1


def test_profile_use_scripted_only_skips_defaults():
    scenario = _scenario(
        {"use_scripted_only": True},
        sects=[{"id": 2, "leader_avatar_id": None, "member_avatar_ids": []}],
    )
    counts = resolve_generation_counts(scenario=scenario, settings=_settings(init_npc_num=9, sect_num=9))
    selected = _select_scenario_existed_sects(
        sects_by_id={idx: _Sect(idx) for idx in range(1, 6)},
        random_sect_count=counts["sect_count"],
        resolved_scenario=scenario,
    )

    assert counts == {"npc_count": 0, "sect_count": 0}
    assert [sect.id for sect in selected] == [2]


def test_no_profile_uses_settings_defaults():
    counts = resolve_generation_counts(scenario=_scenario(None), settings=_settings(init_npc_num=4, sect_num=2))

    assert counts == {"npc_count": 4, "sect_count": 2}


def test_no_scenario_unchanged():
    counts = resolve_generation_counts(scenario=None, settings=_settings(init_npc_num=5, sect_num=1))

    assert counts == {"npc_count": 5, "sect_count": 1}


def test_avatar_pos_explicit_lands_at_coords(mock_llm_managers):
    world = _world()

    avatar = create_scenario_avatar(
        world,
        _scenario_avatar(pos={"x": 3, "y": 4}),
        world.month_stamp,
        preset_id="default",
    )

    assert (avatar.pos_x, avatar.pos_y) == (3, 4)
    assert avatar.tile is world.map.get_tile(3, 4)


def test_avatar_region_id_lands_in_region(mock_llm_managers):
    world = _world()

    avatar = create_scenario_avatar(
        world,
        _scenario_avatar(region_id=101),
        world.month_stamp,
        preset_id="default",
    )

    assert (avatar.pos_x, avatar.pos_y) in set(world.map.regions[101].cors)
    assert avatar.tile is world.map.get_tile(avatar.pos_x, avatar.pos_y)
    assert avatar.born_region_id == 101


def test_loader_rejects_negative_random_npc_count(tmp_path: Path):
    root = _write_scenario(
        tmp_path,
        scenario_patch={
            "initial_state": {
                "year": 1,
                "month": 1,
                "generation_profile": {"random_npc_count": -1},
                "avatars": [_scenario_avatar()],
                "sects": [],
                "relationships": [],
                "world_flags": {},
            }
        },
    )

    with pytest.raises(ScenarioValidationError, match="random_npc_count"):
        load("profile_fixture", scenarios_root=root)


def test_loader_rejects_non_bool_use_scripted_only(tmp_path: Path):
    root = _write_scenario(
        tmp_path,
        scenario_patch={
            "initial_state": {
                "year": 1,
                "month": 1,
                "generation_profile": {"use_scripted_only": "yes"},
                "avatars": [_scenario_avatar()],
                "sects": [],
                "relationships": [],
                "world_flags": {},
            }
        },
    )

    with pytest.raises(ScenarioValidationError, match="use_scripted_only"):
        load("profile_fixture", scenarios_root=root)


def test_loader_rejects_pos_and_region_id_together(tmp_path: Path):
    root = _write_scenario(tmp_path, avatar_patch={"pos": {"x": 1, "y": 1}, "region_id": 101})

    with pytest.raises(ScenarioValidationError, match="mutually exclusive"):
        load("profile_fixture", scenarios_root=root)


def test_loader_rejects_negative_pos_coords(tmp_path: Path):
    root = _write_scenario(tmp_path, avatar_patch={"pos": {"x": -1, "y": 1}})

    with pytest.raises(ScenarioValidationError, match="pos.x"):
        load("profile_fixture", scenarios_root=root)


def test_injection_rejects_out_of_bounds_pos(mock_llm_managers):
    world = _world(width=4, height=4)

    with pytest.raises(ValueError, match="outside map bounds"):
        create_scenario_avatar(
            world,
            _scenario_avatar(pos={"x": 20, "y": 1}),
            world.month_stamp,
            preset_id="default",
        )


def test_injection_rejects_unknown_region_id(mock_llm_managers):
    world = _world()

    with pytest.raises(ValueError, match="unknown region"):
        create_scenario_avatar(
            world,
            _scenario_avatar(region_id=999),
            world.month_stamp,
            preset_id="default",
        )


def test_loader_accepts_schema_version_0_1(tmp_path: Path):
    root = _write_scenario(tmp_path, scenario_patch={"schema_version": "0.1"})

    assert load("profile_fixture", scenarios_root=root).scenario_id == "profile_fixture"
