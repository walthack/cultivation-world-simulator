"""v1.7 M2 — reproducible narration cache (Q3/Q8/Q9).

Generated narration is frozen into `ScriptedScenarioState.narration_cache` keyed
by (scenario_id, event_id, resolved_outcome, content_locale). A reload reuses the
frozen text (no LLM call). The cache is a SIBLING of `state`, never inside it, so
conditions/var_equals can't read generated text (Q12). Authored fallback is never
cached (it is static/reproducible already, Q9).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.scenario.narration_cache import narration_cache_key, resolved_outcome
from src.scenario.state import ScriptedScenarioState
from src.sim.simulator_engine.phases.scripted_scenario import phase_scripted_scenario_tick
from src.systems.time import Month, Year, create_month_stamp


# --- key / outcome helpers ---

class TestCacheKeyHelpers:
    def test_resolved_outcome_prefers_branch_then_choice_else_empty(self):
        assert resolved_outcome("e", {"e": {"branch_id": "b1"}}) == "b1"
        assert resolved_outcome("e", {"e": {"choice_id": "c2"}}) == "c2"
        assert resolved_outcome("e", {"e": {"branch_id": "b1", "choice_id": "c2"}}) == "b1"
        assert resolved_outcome("e", {}) == ""
        assert resolved_outcome("e", None) == ""

    def test_key_includes_locale_so_locales_do_not_collide(self):
        zh = narration_cache_key("sc", "e1", "", "zh-CN")
        en = narration_cache_key("sc", "e1", "", "en-US")
        assert zh != en

    def test_key_distinguishes_outcomes(self):
        assert narration_cache_key("sc", "e1", "b1", "zh-CN") != narration_cache_key("sc", "e1", "b2", "zh-CN")


# --- production-phase cache behaviour ---

def _timeline():
    return [{
        "id": "e1",
        "type": "side_event",
        "narrative_fill": True,
        "narration_fallback": "AUTHORED-FALLBACK",
        "trigger": {"year": 1, "month": 1, "condition": {"always": {}}},
        "effects": [{"type": "set_flag", "flag": "f1"}],
    }]


class CountingFiller:
    def __init__(self, text):
        self.text = text
        self.calls = 0

    def __call__(self, requests, world):
        self.calls += 1
        return {str(se.get("id")): self.text for se in requests}


async def _tick(base_world, sc, filler):
    base_world.world_flags.clear()
    base_world.narrative_filler = filler
    base_world.scripted_scenario = sc
    ctx = SimpleNamespace(month_stamp=create_month_stamp(Year(1), Month.JANUARY))
    return await phase_scripted_scenario_tick(base_world, ctx)


@pytest.mark.asyncio
async def test_miss_generates_and_freezes_into_cache(base_world):
    sc = ScriptedScenarioState(scenario_id="sc", timeline=_timeline())
    filler = CountingFiller("草原风起，他第一次看清这世界。")
    events = await _tick(base_world, sc, filler)

    assert events[0].narration == "草原风起，他第一次看清这世界。"
    assert filler.calls == 1
    # frozen under the composite key
    key = narration_cache_key("sc", "e1", "", base_world_locale())
    assert sc.narration_cache[key] == "草原风起，他第一次看清这世界。"


@pytest.mark.asyncio
async def test_cache_hit_reuses_frozen_text_without_calling_llm(base_world):
    key = narration_cache_key("sc", "e1", "", base_world_locale())
    sc = ScriptedScenarioState(
        scenario_id="sc", timeline=_timeline(), narration_cache={key: "FROZEN"}
    )
    # A filler that would return something different — must NOT be called on a hit.
    filler = CountingFiller("SHOULD-NOT-BE-USED")
    events = await _tick(base_world, sc, filler)

    assert events[0].narration == "FROZEN"
    assert filler.calls == 0


@pytest.mark.asyncio
async def test_reproducible_across_a_simulated_reload(base_world):
    """First run generates+freezes; a reload carrying the same narration_cache
    reuses the frozen text even with a DIFFERENT filler (Q3 reproducibility)."""
    sc1 = ScriptedScenarioState(scenario_id="sc", timeline=_timeline())
    f1 = CountingFiller("FIRST-GENERATION")
    e1 = await _tick(base_world, sc1, f1)
    assert e1[0].narration == "FIRST-GENERATION"

    # simulate reload: new state from an earlier point but carrying the cache
    sc2 = ScriptedScenarioState(
        scenario_id="sc", timeline=_timeline(), narration_cache=dict(sc1.narration_cache)
    )
    f2 = CountingFiller("DIFFERENT-GENERATION")
    e2 = await _tick(base_world, sc2, f2)

    assert e2[0].narration == "FIRST-GENERATION"  # frozen, not regenerated
    assert f2.calls == 0


@pytest.mark.asyncio
async def test_fallback_is_frozen_for_permanent_reproducibility(base_world):
    """Generation failure → authored fallback, frozen into the cache (Q9 permanent
    fallback): once resolved, a later LLM-available reload must NOT regenerate."""
    sc = ScriptedScenarioState(scenario_id="sc", timeline=_timeline())
    events = await _tick(base_world, sc, lambda reqs, w: {})  # filler yields nothing
    assert events[0].narration == "AUTHORED-FALLBACK"
    key = narration_cache_key("sc", "e1", "", base_world_locale())
    assert sc.narration_cache[key] == "AUTHORED-FALLBACK"  # frozen

    # simulated reload with the LLM now available — frozen fallback wins, no regen
    sc2 = ScriptedScenarioState(
        scenario_id="sc", timeline=_timeline(), narration_cache=dict(sc.narration_cache)
    )
    f = CountingFiller("LATE-GENERATION")
    e2 = await _tick(base_world, sc2, f)
    assert e2[0].narration == "AUTHORED-FALLBACK"
    assert f.calls == 0


@pytest.mark.asyncio
async def test_cache_is_sibling_of_state_not_inside_it(base_world):
    """Q12: the generated text must never be reachable via scenario state (which is
    var_equals-readable). The cache lives on its own field, not in `state`."""
    sc = ScriptedScenarioState(scenario_id="sc", timeline=_timeline())
    await _tick(base_world, sc, CountingFiller("SECRET-NARRATION"))

    assert sc.narration_cache  # populated
    import json
    assert "SECRET-NARRATION" not in json.dumps(sc.state, ensure_ascii=False)


def base_world_locale():
    from src.classes.language import language_manager
    return language_manager.current


# --- M2 prerequisite: dispatch exposes the resolved branch outcome ---

class TestBranchOutcomeExposure:
    @pytest.mark.asyncio
    async def test_dispatch_records_selected_branch_for_keying(self):
        from src.scenario.event_dispatcher import EventDispatcher
        from src.scenario.event_handlers.branch_handler import handle_branch

        state = {
            "world": {"year": 1, "month": 1, "world_flags": {"a": True}},
            "scenario_runtime": {"scenario_id": "sc", "triggered_event_ids": []},
        }
        event = {
            "id": "br",
            "type": "branch",
            "trigger": {"year": 1, "month": 1, "condition": {"always": {}}},
            "branches": [
                {"id": "left", "condition": {"world_flag": {"flag": "a"}}, "effects": []},
                {"id": "right", "condition": {"world_flag": {"flag": "b"}}, "effects": []},
            ],
        }
        await EventDispatcher([event], handlers={"branch": handle_branch}).dispatch_month(state)

        outcomes = state["scenario_runtime"]["event_outcomes"]
        assert outcomes["br"] == {"branch_id": "left"}
        # → distinct branches would key distinct narrations
        assert resolved_outcome("br", outcomes) == "left"


# --- the real persistence boundary: save_game → JSON → load_game ---

class TestNarrationCacheSurvivesRealSaveLoad:
    """Guards the P1-a class of bug: reproducibility is silently dead unless the
    cache actually crosses the save_game/load_game JSON boundary (not just the
    in-memory carry)."""

    @pytest.mark.asyncio
    async def test_narration_cache_round_trips_through_save_and_load(self, tmp_path):
        from unittest.mock import patch

        from src.classes.core.world import World
        from src.classes.environment.map import Map
        from src.classes.environment.tile import TileType
        from src.sim.load.load_game import load_game
        from src.sim.save.save_game import save_game
        from src.sim.simulator import Simulator

        def _map():
            m = Map(width=10, height=10)
            for x in range(10):
                for y in range(10):
                    m.create_tile(x, y, TileType.PLAIN)
            return m

        world = World.create_with_db(
            map=_map(),
            month_stamp=create_month_stamp(Year(100), Month.JANUARY),
            events_db_path=tmp_path / "events.db",
        )
        cache = {narration_cache_key("sample", "e1", "", "zh-CN"): "FROZEN-NARRATION"}
        world.scripted_scenario = ScriptedScenarioState(
            scenario_id="sample", timeline=[], narration_cache=dict(cache)
        )

        save_path = tmp_path / "save.json"
        ok, _ = save_game(world, Simulator(world), [], save_path)
        assert ok
        world.event_manager.close()

        # narration_cache must be its own top-level scenario field, never in state.
        import json
        saved = json.loads(save_path.read_text(encoding="utf-8"))
        sc_blob = saved["scripted_scenario"]
        assert sc_blob["narration_cache"] == cache
        assert "narration_cache" not in sc_blob["state"]

        with patch("src.run.load_map.load_cultivation_world_map", return_value=_map()):
            loaded_world, _, _ = load_game(save_path, active_scenario_id="sample")

        assert loaded_world.scripted_scenario.narration_cache == cache
