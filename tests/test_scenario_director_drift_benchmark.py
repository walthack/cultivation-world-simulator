"""v1.9 M5 — long-horizon drift benchmark (the L4 merge gate, Q8).

The spike only proved 4 short rounds. This harness runs a seeded director over 30
in-game years (360 monthly ticks) against a backbone and asserts the L4 safety
contract holds the WHOLE way: every mandatory anchor still fires, no prohibited
outcome ever becomes true, an irreversible fact (a death) is never reversed, and a
late mandatory's precondition is never starved — while the director stays live and
varied. Deterministic (seeded mock director + no random_chance in the timeline), so
it's a reliable CI gate, not a flaky LLM run.
"""

from __future__ import annotations

import random
from types import SimpleNamespace

import pytest

from src.scenario.state import ScriptedScenarioState
from src.sim.simulator_engine.phases.scripted_scenario import phase_scripted_scenario_tick
from src.systems.time import Month, Year, create_month_stamp


MANDATORY_IDS = {"m_start", "m_death", "m_mid", "m_final"}
YEARS = 30  # decades-scale horizon (the spike only proved 4 short rounds)
ENTITIES = ["hero", "villain", "elder"]

BACKBONE = {
    "prohibited_predicates": [{"world_flag": {"flag": "demon_wins", "value": True}}],
    "irreversible_facts": [{"world_flag": {"flag": "hero_dead", "value": True}}],
}


def _bench_timeline():
    # all modellable side_events (plain top-level effects) so the reachability gate
    # engages (rather than fail-closed). m_death sets the irreversible death flag;
    # m_final (the LAST anchor) fires only while `blocker` is unset, so it stays
    # director-starvable the entire run — the gate must protect it every tick.
    return [
        {"id": "m_start", "type": "side_event", "anchor": True, "mandatory": True,
         "trigger": {"year": 1, "month": 1, "condition": {"always": {}}}},
        {"id": "m_death", "type": "side_event", "anchor": True, "mandatory": True,
         "trigger": {"year": 5, "month": 1, "condition": {"always": {}}},
         "effects": [{"type": "set_flag", "flag": "hero_dead"}]},
        {"id": "m_mid", "type": "side_event", "anchor": True, "mandatory": True,
         "trigger": {"year": 15, "month": 1, "condition": {"always": {}}}},
        {"id": "m_final", "type": "side_event", "anchor": True, "mandatory": True,
         "trigger": {"year": 30, "month": 1, "condition": {"world_flag": {"flag": "blocker", "value": False}}}},
    ]


def _benchmark_director(seed: int):
    """A seeded mock director: each month proposes a varied mix of valid beats AND
    adversarial ones (prohibited outcome / resurrection / mandatory-starving flag).
    The gates must accept the valid and reject the adversarial — every month, for 30y."""
    rng = random.Random(seed)
    n = {"i": 0}

    def gen(snapshot):
        n["i"] += 1
        i = n["i"]
        r = rng.random()
        if r < 0.22:                                   # valid scoped fact
            return [{"id": f"f{i}", "narration": f"市井传闻其{i}", "command": {"command": "director_fact", "text": f"事记{i}"}}]
        if r < 0.42:                                   # valid flag (harmless)
            return [{"id": f"sf{i}", "narration": f"风声其{i}", "command": {"command": "director_set_flag", "flag": f"rumor_{i % 9}"}}]
        if r < 0.60:                                   # valid relation nudge
            a, b = rng.sample(ENTITIES, 2)
            return [{"id": f"rc{i}", "narration": f"恩怨其{i}", "command": {"command": "director_relation_change", "a": a, "b": b, "delta": rng.choice([-3, 2, 4])}}]
        if r < 0.73:                                   # ADVERSARIAL: prohibited outcome
            return [{"id": f"dmn{i}", "narration": "魔头欲一统", "command": {"command": "director_set_flag", "flag": "demon_wins"}}]
        if r < 0.85:                                   # ADVERSARIAL: resurrection (reverse irreversible)
            return [{"id": f"res{i}", "narration": "有人欲令死者归来", "command": {"command": "director_clear_flag", "flag": "hero_dead"}}]
        if r < 0.95:                                   # ADVERSARIAL: starve the final mandatory
            return [{"id": f"blk{i}", "narration": "欲断其路", "command": {"command": "director_set_flag", "flag": "blocker"}}]
        return []                                       # quiet month

    return gen


@pytest.mark.asyncio
async def test_long_horizon_drift_benchmark(base_world):
    base_world.world_flags.clear()
    base_world.director_generator = _benchmark_director(seed=1729)
    base_world.scripted_scenario = ScriptedScenarioState(
        scenario_id="drift", timeline=_bench_timeline(), backbone=BACKBONE,
    )

    fired_mandatory: set[str] = set()
    accepted_narrations: list[str] = []
    hero_dead_seen = False
    hero_dead_reverted = False
    blocker_set_while_final_pending = False

    for year in range(1, YEARS + 1):
        for month in Month:
            stamp = create_month_stamp(Year(year), month)
            base_world.month_stamp = stamp
            for ev in await phase_scripted_scenario_tick(base_world, SimpleNamespace(month_stamp=stamp)):
                if ev.id in MANDATORY_IDS:
                    fired_mandatory.add(ev.id)
                elif (ev.id or "").startswith("director:") and ev.narration:
                    accepted_narrations.append(ev.narration)
            # per-tick irreversible-fact watch: once a death is set it must never revert
            hd = bool(base_world.world_flags.get("hero_dead"))
            if hd:
                hero_dead_seen = True
            elif hero_dead_seen:
                hero_dead_reverted = True
            # the gate must never let `blocker` be set WHILE m_final is still pending
            # (after m_final fires the flag is fair game — nothing pending reads it)
            if "m_final" not in fired_mandatory and base_world.world_flags.get("blocker"):
                blocker_set_while_final_pending = True

    flags = base_world.world_flags
    ledger = base_world.scripted_scenario.director_ledger

    # 1. liveness: every mandatory anchor fired despite 30 years of director meddling
    assert fired_mandatory == MANDATORY_IDS

    # 2. no prohibited outcome ever stuck
    assert "demon_wins" not in flags

    # 3. the final mandatory's precondition was never starved while pending (gate
    #    protected it every tick until it fired)
    assert not blocker_set_while_final_pending

    # 4. the death is irreversible — set at y5, never resurrected
    assert flags.get("hero_dead") is True
    assert hero_dead_seen and not hero_dead_reverted

    # 5. beat diversity: the director stayed live and varied, not stuck on one beat
    assert len(set(accepted_narrations)) >= 80

    # 6. the gates actually engaged (safety) AND valid beats landed (liveness)
    reasons = " ".join(r.get("reason", "") for r in ledger if not r.get("accepted"))
    assert "prohibited" in reasons          # demon_wins rejected
    assert "irreversible" in reasons        # resurrection rejected
    assert "mandatory" in reasons           # blocker rejected (would starve m_final)
    assert any(r.get("accepted") for r in ledger)
