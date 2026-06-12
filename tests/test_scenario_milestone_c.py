from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.config.presets import set_active_preset
from src.run.data_loader import reload_all_static_data
from src.run.load_map import load_cultivation_world_map
from src.scenario.injector import (
    inject_scenario_initial_state_into_world,
    inject_scenario_into_world,
)
from src.scenario.scenario_loader import load as load_scenario
from src.sim.avatar_init import make_avatars
from src.sim.load.load_game import load_game, get_events_db_path
from src.sim.save.save_game import save_game
from src.sim.simulator import Simulator
from src.classes.core.world import World
from src.classes.core.sect import sects_by_id
from src.systems.time import Month, Year, create_month_stamp


@pytest.fixture
def liuchao_preset():
    set_active_preset("liuchao")
    reload_all_static_data()
    yield
    set_active_preset("default")
    reload_all_static_data()


def _scenario_world(tmp_path: Path, *, random_npcs: int = 2) -> tuple[World, Simulator, list]:
    scenario = load_scenario("liuchao")
    game_map = load_cultivation_world_map()
    world = World.create_with_db(
        map=game_map,
        month_stamp=create_month_stamp(Year(1), Month.JANUARY),
        events_db_path=get_events_db_path(tmp_path / "scenario.json"),
        start_year=1,
    )
    inject_scenario_into_world(world, scenario)

    existed_sects = [sects_by_id[1]]
    random_avatars = make_avatars(
        world,
        count=random_npcs,
        current_month_stamp=world.month_stamp,
        existed_sects=existed_sects,
    )
    world.avatar_manager.avatars.update(random_avatars)
    inject_scenario_initial_state_into_world(world, scenario)
    world.existed_sects = existed_sects
    world.sect_context.from_existed_sects(existed_sects)
    return world, Simulator(world), existed_sects


def test_scenario_avatars_injected_into_world_avatar_manager(liuchao_preset, tmp_path):
    world, _sim, _sects = _scenario_world(tmp_path)

    for avatar_id in ["cheng-zongyang", "wang-zhe", "xiao-zi"]:
        assert world.avatar_manager.get_avatar(avatar_id) is not None
    assert len(world.avatar_manager.avatars) > 3


def test_scenario_avatar_goldfinger_persona_realm_applied(liuchao_preset, tmp_path):
    world, _sim, _sects = _scenario_world(tmp_path)

    avatar = world.avatar_manager.get_avatar("cheng-zongyang")

    assert avatar is not None
    assert avatar.id == "cheng-zongyang"
    assert avatar.goldfinger is not None
    assert avatar.goldfinger.key == "SHENGSI-GEN"
    assert {persona.name for persona in avatar.personas} >= {"商业谈判", "现代知识", "临机权变"}
    assert avatar.cultivation_progress.level == 1
    assert "来自现代的穿越者" in avatar.backstory
    assert "王哲传功" in avatar.backstory
    assert avatar.long_term_objective.content == "活过草原战场，摆脱奴隶处境，建立能够保护同伴的商政势力。"


def test_scenario_relations_injected_bidirectional(liuchao_preset, tmp_path):
    world, _sim, _sects = _scenario_world(tmp_path)

    cheng = world.avatar_manager.get_avatar("cheng-zongyang")
    wang = world.avatar_manager.get_avatar("wang-zhe")

    assert cheng.relations[wang].friendliness == 50
    assert wang.relations[cheng].friendliness == 50


def test_scripted_scenario_save_roundtrip(liuchao_preset, tmp_path):
    world, sim, existed_sects = _scenario_world(tmp_path)
    save_path = tmp_path / "liuchao-save.json"

    world.scripted_scenario.state["milestone_c_marker"] = {"ok": True}
    world.scripted_scenario.triggered_events.add("liuchao-opening")
    success, _filename = save_game(world, sim, existed_sects, save_path=save_path)

    assert success is True
    raw_save = json.loads(save_path.read_text(encoding="utf-8"))
    assert raw_save["scripted_scenario"]["scenario_id"] == "liuchao"

    loaded_world, _loaded_sim, _loaded_sects = load_game(
        save_path,
        active_scenario_id="liuchao",
    )

    assert loaded_world.scripted_scenario.scenario_id == "liuchao"
    assert loaded_world.scripted_scenario.state["milestone_c_marker"] == {"ok": True}
    assert "liuchao-opening" in loaded_world.scripted_scenario.triggered_events


def test_load_refuses_scenario_mismatch(liuchao_preset, tmp_path):
    world, sim, existed_sects = _scenario_world(tmp_path)
    save_path = tmp_path / "liuchao-save.json"
    success, _filename = save_game(world, sim, existed_sects, save_path=save_path)
    assert success is True

    with pytest.raises(ValueError, match="Save was for scenario liuchao; current boot is sanguo"):
        load_game(save_path, active_scenario_id="sanguo")


def test_load_refuses_no_scenario_flag(liuchao_preset, tmp_path):
    world, sim, existed_sects = _scenario_world(tmp_path)
    save_path = tmp_path / "liuchao-save.json"
    success, _filename = save_game(world, sim, existed_sects, save_path=save_path)
    assert success is True

    with pytest.raises(ValueError, match="Restart with --scenario liuchao"):
        load_game(save_path, active_scenario_id=None)
