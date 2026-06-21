"""Headless scenario playtest harness — drives a scenario package through the REAL
scripted-scenario dispatch loop month by month and prints what a player would see.

Usage:
    .venv/bin/python tools/playtest_scenario.py <scenario_id> [months] [flag=val ...]

  flag=val pre-sets a world_flag before the run (e.g. cheng_chose_merchant=1) so you can
  drive a specific branch. The L4 Narrative Director (LLM) is NOT exercised here — this
  shows the deterministic scripted spine (mandatory anchors / branches / storylines /
  narration fallback) a player meets with no LLM key. Boots no server/frontend.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.scenario.scenario_loader import load
from src.scenario.event_dispatcher import EventDispatcher
from src.sim.simulator_engine.phases.scripted_scenario import _HANDLERS
from src.scenario.state_access import get_active_storylines, get_world_flags


def _build_state(scenario, controlled="cheng-zongyang", preset_flags=None):
    initial = scenario.scenario["initial_state"]
    avatars = {
        a["id"]: {"id": a["id"], "name": a["surname"] + a["given_name"], "realm": a.get("realm"),
                  "alive": True, "skills": [], "stats": {}, "items": [], "sect_id": a.get("sect_id")}
        for a in initial["avatars"]
    }
    if controlled not in avatars:
        controlled = next(iter(avatars))
    relations = {}
    for r in initial.get("relationships", []):
        a, b = sorted([r["a"], r["b"]])
        relations[f"{a}:{b}"] = r["value"]
    flags = dict(initial.get("world_flags", {}))
    flags.update(preset_flags or {})
    return {
        "player": avatars[controlled],
        "npcs": {k: v for k, v in avatars.items() if k != controlled},
        "controlled_avatar": controlled,
        "relations": relations,
        "world": {"year": initial.get("year", 1), "month": initial.get("month", 1), "world_flags": flags},
        "scenario_runtime": {"scenario_id": scenario.scenario_id, "triggered_event_ids": [], "event_outcomes": {}},
    }


async def _play(scenario_id, months, preset_flags):
    scenario = load(scenario_id)
    state = _build_state(scenario, preset_flags=preset_flags)
    dispatcher = EventDispatcher(scenario.timeline, handlers=dict(_HANDLERS))
    mandatory = {e["id"] for e in scenario.timeline if e.get("mandatory")}
    fired_mandatory, fired_all = set(), []

    print(f"\n=== PLAYTEST: {scenario_id} ({scenario.title}) — {months} months ===")
    if preset_flags:
        print(f"  preset flags: {preset_flags}")
    y, m = state["world"]["year"], state["world"]["month"]
    for _ in range(months):
        for ev in await dispatcher.dispatch_month(state, year=y, month=m):
            eid = ev.get("id", "")
            tag = "★MANDATORY" if eid in mandatory else ("◆" + ev.get("type", ""))
            text = ev.get("narration_fallback") or ev.get("description") or ""
            print(f"  Y{y}M{m:<2} [{tag}] {ev.get('name','')} — {text[:64]}")
            fired_all.append(eid)
            if eid in mandatory:
                fired_mandatory.add(eid)
        m = m + 1 if m < 12 else 1
        y = y + (0 if m != 1 else 1)

    lines = get_active_storylines(state)
    print(f"  → mandatory anchors fired: {len(fired_mandatory)}/{len(mandatory)}"
          + ("  ✅ ALL" if fired_mandatory == mandatory else f"  ⚠ MISSING {mandatory - fired_mandatory}"))
    print(f"  → active storylines: {list(lines)}")
    print(f"  → world flags set: {sorted(k for k, v in get_world_flags(state).items() if v)}")
    return fired_mandatory == mandatory


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    scenario_id = sys.argv[1]
    months = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 16
    preset_flags = {}
    for arg in sys.argv[3:]:
        if "=" in arg:
            k, v = arg.split("=", 1)
            preset_flags[k] = (v not in ("0", "false", "False"))
    ok = asyncio.run(_play(scenario_id, months, preset_flags))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
