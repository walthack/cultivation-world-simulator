from __future__ import annotations

from src.classes.core.world import World
from src.classes.environment.map import Map
from src.classes.environment.tile import TileType
from src.scenario.state import ScriptedScenarioState
from src.systems.time import Month, Year, create_month_stamp


def _map() -> Map:
    game_map = Map(width=4, height=4)
    for x in range(4):
        for y in range(4):
            game_map.create_tile(x, y, TileType.PLAIN)
    return game_map


def test_game_start_request_scenario_id_overrides_cli_default(monkeypatch, tmp_path):
    from src.server import main as server_main

    resolved = server_main.resolve_scenario_for_start(
        server_main.GameStartRequest(scenario_id="sanguo")
    )
    monkeypatch.setattr(server_main.runtime, "active_scenario", resolved)
    monkeypatch.setattr(server_main.runtime, "active_scenario_explicit", True)

    world = server_main.ScenarioInjectedWorld.create_with_db(
        map=_map(),
        month_stamp=create_month_stamp(Year(1), Month.JANUARY),
        events_db_path=tmp_path / "events.db",
        start_year=1,
    )

    assert isinstance(world.scripted_scenario, ScriptedScenarioState)
    assert world.scripted_scenario.scenario_id == "sanguo"


def test_game_start_default_empty_and_null_disable_scenario(monkeypatch, tmp_path):
    from src.server import main as server_main

    requests = [
        server_main.GameStartRequest(scenario_id="default"),
        server_main.GameStartRequest(scenario_id=""),
        server_main.GameStartRequest.model_validate({"scenario_id": None}),
    ]

    for index, request in enumerate(requests):
        resolved = server_main.resolve_scenario_for_start(request)
        monkeypatch.setattr(server_main.runtime, "active_scenario", resolved)
        monkeypatch.setattr(server_main.runtime, "active_scenario_explicit", True)
        world = server_main.ScenarioInjectedWorld.create_with_db(
            map=_map(),
            month_stamp=create_month_stamp(Year(1), Month.JANUARY),
            events_db_path=tmp_path / f"events-{index}.db",
            start_year=1,
        )
        assert world.scripted_scenario is None


def test_game_start_omitted_scenario_id_uses_cli_default(monkeypatch):
    from src.scenario.scenario_loader import load
    from src.server import main as server_main

    cli_default = load("liuchao")
    monkeypatch.setattr(server_main, "ACTIVE_SCENARIO", cli_default)

    resolved = server_main.resolve_scenario_for_start(server_main.GameStartRequest())

    assert resolved.scenario_id == "liuchao"
