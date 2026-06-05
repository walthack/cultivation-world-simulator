from src.scenario.scenario_loader import load


STAGE_2C_DYNASTY_IDS = {"qin", "han", "jin", "song"}


def _stage_2c_dynasty_events():
    scenario = load("liuchao")
    return [
        event
        for event in scenario.timeline
        if event.get("type") == "main" and event.get("dynasty_id") in STAGE_2C_DYNASTY_IDS
    ]


def test_liuchao_stage_2c_timeline_has_event_per_target_dynasty():
    dynasty_ids = {event.get("dynasty_id") for event in _stage_2c_dynasty_events()}

    assert STAGE_2C_DYNASTY_IDS <= dynasty_ids


def test_liuchao_stage_2c_timeline_event_count_is_expected_range():
    stage_2c_ids = {
        "qin-guanzhong-muster",
        "han-luoyang-edict",
        "jin-jiankang-clan-council",
        "song-linan-river-tax",
        "han-north-border-watchfires",
        "qin-changan-law-revision",
    }
    events = [event for event in _stage_2c_dynasty_events() if event["id"] in stage_2c_ids]

    assert 5 <= len(events) <= 10


def test_liuchao_stage_2c_timeline_loads_without_schema_error():
    scenario = load("liuchao")

    assert scenario.timeline
