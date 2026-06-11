from src.config.presets import (
    get_preset_dynasty_ids,
    get_preset_region_ids,
    get_preset_regions,
    get_preset_realm_order,
    get_preset_realms,
    get_preset_sect_ids,
)
from src.scenario.scenario_loader import load


OPENING_EVENT_IDS = [
    "liuchao-opening",
    "duan-qiang-falls",
    "cheng-captured-by-qin",
    "first-contact-taiyi",
]


def test_liuchao_phase_1_timeline_is_minimal_canonical_opening():
    scenario = load("liuchao")

    assert [event["id"] for event in scenario.timeline] == OPENING_EVENT_IDS


def test_liuchao_phase_1_timeline_references_known_presets():
    scenario = load("liuchao")
    dynasty_ids = get_preset_dynasty_ids("liuchao")
    region_ids = get_preset_region_ids("liuchao")

    for event in scenario.timeline:
        assert event.get("dynasty_id") in dynasty_ids
        region_id = event.get("trigger", {}).get("at_region_id")
        if region_id is not None:
            assert region_id in region_ids


def test_liuchao_phase_1_timeline_loads_without_schema_error():
    scenario = load("liuchao")

    assert len(scenario.timeline) == 4


def test_liuchao_phase_1_timeline_contains_no_adult_content_markers():
    scenario = load("liuchao")
    serialized = str(scenario.timeline)

    assert all(marker not in serialized for marker in ("H场景", "18+", "性爱", "情色"))


def test_liuchao_initial_avatar_references_resolve():
    scenario = load("liuchao")
    realm_ids = set(get_preset_realm_order("liuchao"))
    region_ids = get_preset_region_ids("liuchao")
    sect_ids = get_preset_sect_ids("liuchao")

    for avatar in scenario.scenario["initial_state"]["avatars"]:
        assert avatar["realm"] in realm_ids
        assert avatar["location_region_id"] in region_ids
        assert avatar["sect_id"] is None or avatar["sect_id"] in sect_ids


def test_liuchao_progression_cultivation_axis_matches_realm_preset():
    scenario = load("liuchao")
    axes = scenario.scenario["initial_state"]["generation_profile"]["progression_profile"]["axes"]
    cultivation_axis = next(axis for axis in axes if axis["id"] == "taiyi_cultivation")

    assert cultivation_axis["tiers"] == [realm["display_name"] for realm in get_preset_realms("liuchao")]


def test_liuchao_regions_have_no_placeholder_content():
    regions = get_preset_regions("liuchao")

    assert all("TODO" not in region["description"] for region in regions)
    assert all("placeholder" not in region["tags"] for region in regions)
