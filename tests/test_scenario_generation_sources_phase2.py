from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.classes.core.sect import sects_by_id
from src.classes.gender import Gender
from src.classes.persona import _resolved_persona_candidates
from src.config.presets import set_active_preset
from src.run.data_loader import reload_all_static_data
from src.run.load_map import load_cultivation_world_map
from src.scenario.source_resolver import (
    clear_active_scenario_source,
    resolve_source,
    set_active_scenario_source,
)
from src.server.init_flow import _select_existed_sects
from src.utils import name_generator


LIUCHAO_LAST_NAMES = {"程", "王", "紫", "萧", "秦"}
LIUCHAO_MALE_NAMES = {"宗扬", "哲", "羽", "玄", "昭"}
LIUCHAO_PERSONAS = {"谋略", "现代知识", "野心", "灰色道德", "忠义", "神秘"}
LIUCHAO_SECTS = {
    "太乙真宗",
    "王氏玄门",
    "谢氏清府",
    "兰亭清谈社",
    "栖霞禅院",
    "茅山道观",
    "北府流亡盟",
    "富春山隐宗",
    "竹林玄社",
    "秦淮江左会",
}
LIUCHAO_REGIONS = {
    "临安",
    "江南",
    "洛阳",
    "北境",
    "建康",
    "成都",
    "巴蜀群山",
    "长安",
    "关中",
    "太一山",
}


def _scenario(source_key: str, source: str) -> SimpleNamespace:
    return SimpleNamespace(
        scenario_id="phase2_fixture",
        preset_id="liuchao",
        scenario={
            "schema_version": "1.2",
            "scenario_id": "phase2_fixture",
            "world_preset": {"preset_id": "liuchao"},
            "initial_state": {
                "generation_profile": {
                    "generation_sources": {source_key: source},
                }
            },
        },
    )


@pytest.fixture(autouse=True)
def reset_generation_sources():
    set_active_preset("default")
    clear_active_scenario_source()
    reload_all_static_data()
    yield
    clear_active_scenario_source()
    set_active_preset("default")
    reload_all_static_data()


def _name_pool() -> tuple[list[str], list[str]]:
    return (
        list(name_generator._name_manager.common_last_names),
        list(name_generator._name_manager.common_given_names[Gender.MALE]),
    )


def _region_names() -> set[str]:
    return {
        region.name
        for region in load_cultivation_world_map().regions.values()
        if region.get_region_type() != "sect"
    }


def test_no_scenario_default_sandbox_generation_is_unchanged():
    default_names = _name_pool()
    default_personas = {persona.name for persona in _resolved_persona_candidates()}
    default_sects = {sect.id: sect.name for sect in sects_by_id.values()}
    default_regions = _region_names()

    clear_active_scenario_source()
    reload_all_static_data()

    assert _name_pool() == default_names
    assert {persona.name for persona in _resolved_persona_candidates()} == default_personas
    assert {sect.id: sect.name for sect in sects_by_id.values()} == default_sects
    assert _region_names() == default_regions


@pytest.mark.parametrize("source", ["scenario", "default", "mixed"])
def test_npc_name_source_switching(source: str):
    default_last_names, default_male_names = _name_pool()
    set_active_scenario_source(_scenario("npc_names", source))
    name_generator.reload()
    last_names, male_names = _name_pool()

    if source == "scenario":
        assert set(last_names) == LIUCHAO_LAST_NAMES
        assert set(male_names) == LIUCHAO_MALE_NAMES
    elif source == "default":
        assert last_names == default_last_names
        assert male_names == default_male_names
    else:
        assert last_names[: len(LIUCHAO_LAST_NAMES)] == ["程", "王", "紫", "萧", "秦"]
        assert male_names[: len(LIUCHAO_MALE_NAMES)] == ["宗扬", "哲", "羽", "玄", "昭"]
        assert set(default_last_names) <= set(last_names)
        assert set(default_male_names) <= set(male_names)


@pytest.mark.parametrize("source", ["scenario", "default", "mixed"])
def test_structured_persona_source_switching(source: str):
    default_names = {persona.name for persona in _resolved_persona_candidates()}
    set_active_scenario_source(_scenario("personas", source))
    reload_all_static_data()
    names = {persona.name for persona in _resolved_persona_candidates()}

    if source == "scenario":
        assert names == LIUCHAO_PERSONAS
    elif source == "default":
        assert names == default_names
    else:
        assert LIUCHAO_PERSONAS <= names
        assert default_names <= names


@pytest.mark.parametrize("source", ["scenario", "default", "mixed"])
def test_sect_source_switching(source: str):
    default_names = {sect.name for sect in sects_by_id.values()}
    set_active_scenario_source(_scenario("sects", source))
    reload_all_static_data()
    selected = _select_existed_sects(sects_by_id=sects_by_id, needed_sects=99)
    names = {sect.name for sect in selected}

    if source == "scenario":
        assert names == LIUCHAO_SECTS
    elif source == "default":
        assert names == default_names
    else:
        assert LIUCHAO_SECTS <= names
        assert len(selected) == len(sects_by_id)
        assert len(selected) > len(LIUCHAO_SECTS)


@pytest.mark.parametrize("source", ["scenario", "default", "mixed"])
def test_region_name_source_switching(source: str):
    default_names = _region_names()
    set_active_scenario_source(_scenario("regions", source))
    names = _region_names()

    if source == "scenario":
        assert names <= LIUCHAO_REGIONS
        assert LIUCHAO_REGIONS <= names
    elif source == "default":
        assert names == default_names
    else:
        assert LIUCHAO_REGIONS <= names
        assert names & default_names


def test_mixed_resolver_merges_scenario_first_then_default():
    set_active_scenario_source(_scenario("sects", "mixed"))

    handle = resolve_source("sects")
    sect_ids = handle.data["sect_ids"]

    assert handle.source == "mixed"
    assert sect_ids[:10] == list(range(1, 11))
    assert set(range(1, 15)) <= set(sect_ids)
