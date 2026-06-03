# Milestone C Spec — Scenario World Injection + Save/Load

Date: 2026-06-03
Author: Hassan
Status: Ready for codex implementation
Master signoff: 2026-06-03 13:07 SGT (Milestone roadmap) + 20:27 SGT (execute-to-v0.4 autonomous directive)
Branch: `feat/scenario-engine-milestone-C` (branched off milestone-B HEAD `2c461ea0`)

## Goal

Push scenario data from the `scripted_scenario.state` shadow into the real world:
- Scenario `initial_state.avatars[*]` become real `Avatar` objects in `world.avatar_manager` (so they show in the avatar grid, can be roleplayed, can act in the simulator).
- Scenario `initial_state.relationships[*]` become real `avatar.relations` edges between the injected avatars (so social systems see them).
- `ScriptedScenarioState` (scenario_id, state, triggered_events) round-trips through save/load so a player can save mid-scenario and restore correctly.

This closes the "scenario is mostly decorative" gap that Milestone A intentionally left behind. After Milestone C, scenario data is a first-class citizen of the world state.

## Decision Matrix (locked)

| Q | Decision |
|---|---|
| Q1 avatar timing | Inject AFTER `init_flow`'s normal random-NPC generation. Scenario avatars are **additive** — they coexist with the user-requested `init_npc_num` random NPCs. |
| Q2 avatar IDs | Honor the scenario's avatar IDs (e.g. `cheng-zongyang`) verbatim. AvatarManager.register_avatar accepts pre-set IDs. |
| Q3 missing scenario refs | If `scenario.avatar.goldfinger_id` references an unknown goldfinger in the preset, FAIL boot (do not silently default). Same for sect_id / persona_keys. |
| Q4 relation directionality | Apply relations bidirectionally — if scenario has `{a: cheng-zongyang, b: wang-zhe, value: 5}`, BOTH `cheng-zongyang.relations[wang-zhe] = 5` AND `wang-zhe.relations[cheng-zongyang] = 5`. |
| Q5 save scope | Persist `scripted_scenario.scenario_id`, `scripted_scenario.state` (entire dict), and `triggered_events` (as sorted list). Do NOT persist `timeline` — re-load from scenario file via scenario_loader on game load. |
| Q6 load with scenario mismatch | If save has scenario_id "liuchao" but server booted with `--scenario sanguo`, refuse to load with explicit error. If save has scenario_id "liuchao" and server has no `--scenario` flag, refuse to load (require flag for restore). |
| Q7 load default save behavior | If save has no `scripted_scenario` key (legacy save from before Milestone C), load proceeds with `world.scripted_scenario = None` regardless of current `--scenario` flag (don't override on load — leave runtime as whatever boot configured). |

## Scope (3 deliverables)

### 1. Avatar injection
- Extend `src/scenario/injector.py::inject_scenario_into_world(world, resolved)` (or add a follow-up `inject_scenario_avatars(world, resolved, current_month_stamp)` if cleaner) to walk `resolved.scenario["initial_state"]["avatars"]` and create real `Avatar` objects.
- For each scenario avatar:
  - Construct `Avatar` honoring: `id`, `surname`, `given_name`, `gender`, `age`, `sect_id` (None or int), `realm` (string realm_id from preset), `stage`, `level`, `backstory`, `persona_traits` (list of strings — map to existing Persona keys in preset), `goldfinger_id` (key in preset goldfingers), `long_term_objective`.
  - Use the existing `create_avatar_from_request` helper if its signature can accept these fields, OR write a new `create_scenario_avatar(world, scenario_avatar_dict, current_month_stamp)` helper alongside it. Codex picks based on least intrusion.
  - Register via `world.avatar_manager.register_avatar(avatar, is_newly_born=True)` (mirror the D1 bulk-import pattern).
- Injection happens AFTER `init_flow` finishes random NPC generation. Implementation point: extend `ScenarioInjectedWorld.create_with_db` is too early; the actual hook should be a NEW step in `init_flow.py` that runs after the existing random NPC generation phase, when `world.scripted_scenario is not None`.

### 2. Relation injection
- After all scenario avatars are registered, walk `resolved.scenario["initial_state"]["relationships"]`.
- For each `{a, b, value}`: look up `avatar_a = world.avatar_manager.get_avatar(a)`, `avatar_b = world.avatar_manager.get_avatar(b)`, then set `avatar_a.relations[avatar_b] = Relation(value=value)` AND `avatar_b.relations[avatar_a] = Relation(value=value)`.
- If either avatar is missing (scenario data inconsistency), FAIL with a clear error pointing at the bad relation entry. Don't silently skip.
- Look at how existing avatar relation initialization works (search for "avatar.relations[" assignment patterns in src/sim/) and follow the existing Relation object construction.

### 3. Save/load persistence
- Save (`src/sim/save/save_game.py`):
  - In the save_data dict construction, add `"scripted_scenario"` key when `world.scripted_scenario is not None`. Structure:
    ```python
    save_data["scripted_scenario"] = {
        "scenario_id": world.scripted_scenario.scenario_id,
        "state": dict(world.scripted_scenario.state),
        "triggered_events": sorted(world.scripted_scenario.triggered_events),
    }
    ```
  - If `world.scripted_scenario is None`, omit the key entirely (legacy saves stay clean).
- Load (`src/sim/load/load_game.py`):
  - Read `load_data.get("scripted_scenario")`. If present:
    - Extract scenario_id from save. Compare with `ACTIVE_SCENARIO_ID` (current boot flag).
    - If they differ OR ACTIVE_SCENARIO_ID is None, raise a clear error: "Save was for scenario X but server booted with scenario Y / no scenario. Restart with `--scenario X` to load this save."
    - If they match, after the World is reconstructed: `world.scripted_scenario = ScriptedScenarioState(scenario_id=..., timeline=resolved.timeline, state=loaded_state, triggered_events=set(loaded_triggered))`. Re-fetch timeline from `scenario_loader.load(scenario_id)` (fresh from scenario file — don't trust save for static data).
  - If absent (legacy save / no-scenario save): don't touch `world.scripted_scenario`; it stays at whatever boot set (None or fresh injected scenario).

## Edge cases / Failure modes to handle

| Scenario | Behavior |
|---|---|
| Boot `--scenario liuchao` + load liuchao save | ✅ load succeeds, scripted_scenario state restored |
| Boot `--scenario sanguo` + load liuchao save | ❌ refuse load with explicit error |
| Boot no flag + load liuchao save | ❌ refuse load — "restart with `--scenario liuchao`" |
| Boot `--scenario liuchao` + load no-scenario save | ✅ load succeeds, scripted_scenario stays at boot-injected state (current boot's scenario wins) |
| Boot no flag + load no-scenario save | ✅ load succeeds, scripted_scenario stays None (default) |
| Scenario avatar references missing goldfinger | ❌ boot fails (loader validation should catch this — verify) |
| Scenario relation references missing avatar | ❌ injection fails with pointer at bad entry |
| Save mid-scenario then advance + load: triggered_events restored | ✅ events that already fired don't re-fire after load |

## Tests required

### Backend (≥6 new tests in `tests/test_scenario_milestone_c.py`)
1. `test_scenario_avatars_injected_into_world_avatar_manager` — boot with liuchao, after init: `world.avatar_manager.get_avatar("cheng-zongyang") is not None`; verify all 3 liuchao avatars present alongside random NPCs (total NPCs > scenario count)
2. `test_scenario_avatar_goldfinger_persona_realm_applied` — verify injected avatar has correct goldfinger / persona_traits / realm from scenario.json
3. `test_scenario_relations_injected_bidirectional` — verify `cheng-zongyang.relations[wang-zhe]` value matches scenario relationship + bidirectional
4. `test_scripted_scenario_save_roundtrip` — boot liuchao, advance state (set a key in scripted_scenario.state, mark an event triggered), save, load → state and triggered_events match
5. `test_load_refuses_scenario_mismatch` — save with liuchao, attempt load while booted with --scenario sanguo → raises explicit error
6. `test_load_refuses_no_scenario_flag` — save with liuchao, attempt load with no `--scenario` flag → raises explicit error

### Frontend
- No new vitest required for this milestone — visibility was Milestone B's job. Verify existing scenario UI tests still pass.

## Files expected to touch

New:
- `tests/test_scenario_milestone_c.py` — 6 backend tests above
- `docs/adr/ADR-009-scenario-world-injection-and-save-load.md`

Modified:
- `src/scenario/injector.py` — add avatar + relation injection (or factor into a new module if too long)
- `src/scenario/state.py` — possibly extend `ScriptedScenarioState` if dataclass needs new fields (unlikely; should work as-is)
- `src/server/init_flow.py` — add scenario avatar/relation injection step AFTER random NPC generation
- `src/server/main.py` — wire the new injection step into the flow if it lives outside ScenarioInjectedWorld
- `src/sim/save/save_game.py` — persist scripted_scenario
- `src/sim/load/load_game.py` — restore scripted_scenario with scenario_id consistency check
- Possibly `src/classes/core/world.py` — if avatar.relations init needs a helper

Untouched (forbidden):
- `.venv/`
- `tests/test_game_init_integration.py` (pre-existing failures)
- Engine semantic changes (`src/scenario/condition_evaluator.py`, `effect_applier.py`, `event_dispatcher.py`) — these are stable contract code
- Mutation endpoints (no API changes — Milestone B finished the read-only API)
- Frontend code (scenario UI is done in Milestone B)

## Acceptance criteria

1. Boot `--scenario liuchao` → `curl /api/v1/query/world/state` (or new debug endpoint) shows cheng-zongyang / wang-zhe / xiao-zi alongside the user's random NPCs in the avatar list.
2. Boot `--scenario liuchao` → `cheng-zongyang.relations.get(wang-zhe)` returns the scenario-defined relation value, bidirectional.
3. Boot `--scenario sanguo` → liu-bei / cao-cao / sun-quan injected as real avatars; their scenario relations applied.
4. Boot no `--scenario` → no scenario-avatar injection; no relation injection (default game flow unchanged).
5. Save mid-scenario → save file contains `"scripted_scenario": {scenario_id, state, triggered_events}` key.
6. Load matching scenario → `world.scripted_scenario` restored with same state and triggered_events.
7. Load mismatched scenario → explicit error.
8. Load no-scenario save with `--scenario liuchao` → load succeeds, scripted_scenario stays at boot-injected state.
9. Backend pytest: 125 → ≥ 131 (+6 milestone C tests). Existing 130-test suite unchanged.
10. Full pytest: baseline 1633 → 1633 + 6 = 1639 (3 pre-existing failures unchanged).
11. No regressions in default game (boot without `--scenario`, no save with scenario_key, scripted_scenario stays None).
12. ADR-009 lands documenting avatar injection timing, relation directionality, save/load scenario_id consistency strategy, edge case table.

## ADR-009 must cover

- Avatar injection timing (post-random-NPC, additive)
- Avatar ID honor strategy (scenario IDs verbatim)
- Relation directionality (bidirectional automatic)
- Save scope decision (state + triggered only, no timeline)
- Load consistency strategy (scenario_id must match boot flag, no silent fallback)
- Edge case table (the one in the spec above)

## Commit grouping

~3-4 commits on `feat/scenario-engine-milestone-C`:
1. `feat: Milestone C — scenario avatar injection into world.avatar_manager` (avatar injection only + tests 1-2)
2. `feat: Milestone C — scenario relation injection (bidirectional)` (relation injection + test 3)
3. `feat: Milestone C — ScriptedScenarioState save/load persistence` (save/load + tests 4-6)
4. `docs: Milestone C — ADR-009 + spec finalization` (ADR + any spec edit)

If `.git/index.lock` blocks, write all + report unstaged.

## Reporting format
```
WROTE (new files):
  <list>
MODIFIED (existing files):
  <list>
NEW BACKEND TEST COUNT: 125 -> <N>
COMMITS: <sha + subject list> | unstaged | blocked
ADR PATH: docs/adr/ADR-009-...
EDGE CASE HANDLING NOTES: <one line per Q1-Q7 confirming behavior>
DEVIATIONS FROM SPEC: <list>
```

"PARTIAL — done: X, remaining: Y" if you bail.
