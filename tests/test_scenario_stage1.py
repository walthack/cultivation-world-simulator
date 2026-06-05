from src.config.presets import (
    get_preset_realm_order,
    get_preset_sect_ids,
    set_active_preset,
)
from src.server.init_flow import _select_existed_sects
from src.utils import name_generator
from src.classes.gender import Gender
from src.scenario.scenario_loader import load


class _Sect:
    def __init__(self, sect_id: int):
        self.id = sect_id


def test_default_preset_sect_pool_preserves_current_ids():
    set_active_preset("default")
    sect_ids = get_preset_sect_ids("default")

    assert sect_ids == list(range(1, 15))

    selected = _select_existed_sects(
        sects_by_id={sect_id: _Sect(sect_id) for sect_id in sect_ids},
        needed_sects=14,
    )
    assert sorted(sect.id for sect in selected) == sect_ids


def test_default_preset_realm_order_preserves_current_order():
    set_active_preset("default")

    assert get_preset_realm_order("default") == [
        "QI_REFINEMENT",
        "FOUNDATION_ESTABLISHMENT",
        "CORE_FORMATION",
        "NASCENT_SOUL",
    ]


def test_liuchao_preset_changes_generated_name_style():
    set_active_preset("liuchao")
    try:
        name_generator.reload()
        names = {name_generator.get_random_name(Gender.MALE) for _ in range(20)}
    finally:
        set_active_preset("default")
        name_generator.reload()

    assert any(name.startswith(("程", "王", "紫", "萧", "秦")) for name in names)
    assert any(given in name for name in names for given in ("宗扬", "哲", "羽", "玄", "昭"))


def test_scenario_loader_loads_sample_scenario():
    scenario = load("sample")

    assert scenario.scenario_id == "sample"
    assert scenario.preset_id == "default"
    assert [event["id"] for event in scenario.timeline] == ["sample-main-event"]
