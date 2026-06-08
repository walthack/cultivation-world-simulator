# Spec: v1.2.3 — Game Loop Pickle Fix (hotfix + regression guard)

**Status**: draft (Hassan, 2026-06-08, after bisect + RCA)
**Type**: **hotfix** — single root-cause fix + permanent regression guard.
No schema change, no API change, no preset content change.
**Version**: v1.2.3 (off `main` @ `v1.2.2-sects-pool-warning`)
**Owner**: codex (implementation + regression test); Hassan reviews + verifies + tags
**Branch**: `fix/game-loop-pickle-v1.2.3`
**Tag target**: `v1.2.3-game-loop-fix`

---

## 1. Why (incident summary)

During v1.2.2 narrative verification (2026-06-07, Hassan + master playthrough through Playwright UI) the world refused to advance past `1年1月`. Backend log spammed:

```
Game loop error: cannot pickle 'sqlite3.Connection' object
```

≥ 2980 occurrences during a 35-minute playthrough; no month tick; no
events past the four init-time long-term-objective entries.

This breaks every player workflow that involves a scenario being
active (the game loop is supposed to auto-step months once the user
clicks Start). All v1.2.2 narrative work (Phase A-F, Theme leakage,
Blind classification, v1.3 priority decision) is **blocked** until
this is fixed.

## 2. Bisect

| Tag | Status |
|---|---|
| `v1.0.0-final` (`f7abac60`) | ✅ GOOD — world advances |
| `v1.0.1-final` (`979c5475`) | (skipped, expected good — content only avatar pos fix) |
| `v1.1.0-final` (`86269804`) | ❌ BAD — first bad commit |
| `v1.2.0-final` → `v1.2.2-sects-pool-warning` | ❌ BAD (carried) |

`git bisect run` confirmed `86269804` ("feat: v1.1 — Scenario World Generation Control") is the **first bad commit**.

## 3. Root cause (traced via `~/cws-playtest-v1.0/logs/20260608.log`)

Call stack at the moment of crash:

1. `src/server/loop_runtime.py:161` — `events = await runtime.run_mutation(sim.step)`
2. `src/server/runtime/session.py:225` — `return await result`
3. `src/sim/simulator_engine/simulator.py:92` — `await scripted_scenario.phase_scripted_scenario_tick(self.world, ctx)`
4. `src/sim/simulator_engine/phases/scripted_scenario.py:105` — `await dispatcher.dispatch_month(...)`
5. `src/scenario/event_dispatcher.py:104` — `await result`
6. `src/scenario/event_handlers/side_event_handler.py:9` — `apply_effects(state, event.get("effects", []) or [])`
7. `src/scenario/effect_applier.py:193` — `before = copy.deepcopy(state)`

`copy.deepcopy(state)` uses the pickle protocol internally. The
`state` dict built in `_build_dispatch_state` at
`src/sim/simulator_engine/phases/scripted_scenario.py:49` includes a
direct reference to `world`:

```python
# scripted_scenario.py:_build_dispatch_state
state = {
    **scenario_state,
    "player": _scenario_player(world, scenario_state),
    "world": world,                       # ←──── World holds EventStorage
    "roleplay_session": ...,
    "scenario_runtime": runtime,
    "scripted_scenario_state": scenario_state,
}
```

`world` holds an `EventStorage` (`src/classes/event_storage.py:61`)
which holds `self._conn: sqlite3.Connection` — Python's sqlite3
Connection objects are **not picklable**. `copy.deepcopy` therefore
raises `TypeError: cannot pickle 'sqlite3.Connection' object` and the
game loop swallows it as `Game loop error: ...` — the world silently
freezes at the current month.

This phase was introduced by the v1.1 commit (Scenario World
Generation Control); v1.0 had no scripted scenario tick, so deepcopy
never ran on a `state` carrying `world`, and the bug never surfaced.
v1.0 was bug-free not because effect rollback was safe but because
the bad code path was unreachable.

## 4. Fix (minimal, no behavior change for downstream callers)

The fix must achieve **two** things:

### 4.1 Effect rollback stays semantically correct
`apply_effects` is supposed to roll `state` back on exception, so the
scenario can attempt an effect, fail, and resume cleanly. Today's
implementation:

```python
def apply_effects(state, effects):
    before = copy.deepcopy(state)       # ← fails on sqlite Connection
    try:
        for effect in effects:
            ...
            _apply_one(state, effect)
    except Exception:
        if isinstance(state, dict) and isinstance(before, dict):
            state.clear(); state.update(before)
        raise
    return state
```

The rollback only ever puts the inner mutable scenario keys back
(`npcs`, `relations`, `world_flags`, `triggered_event_ids`,
`blocked_event_ids`, `event_outcomes`). It does not need to "rollback"
the embedded `world` / `player` / `roleplay_session` /
`scripted_scenario_state` references — those are either read-only
context or aliases to the same underlying mutable dict.

Recommended fix path **A (preferred)**: deepcopy only the rollback-
relevant scenario keys, not the whole dict.

```python
ROLLBACK_KEYS = (
    "npcs",
    "relations",
    "world_flags",
    "triggered_event_ids",
    "blocked_event_ids",
    "event_outcomes",
    "scenario_runtime",
    "scripted_scenario_state",
)

def apply_effects(state, effects):
    before = {k: copy.deepcopy(state[k]) for k in ROLLBACK_KEYS if k in state}
    try:
        for effect in effects:
            if not isinstance(effect, dict):
                raise EffectError(f"effect must be an object: {effect!r}")
            _apply_one(state, effect)
    except Exception:
        if isinstance(state, dict):
            for k, snapshot in before.items():
                state[k] = snapshot
        raise
    return state
```

Codex finalizes the exact key set after verifying which keys are
mutated by `_apply_one` (read the effect handlers; the canonical set
is roughly the keys in §3 list above, but codex confirms before
finalizing).

Alternative path **B**: filter `world` / `player` etc. out of the
dispatch state before passing to `apply_effects`. Higher risk (breaks
side-event handlers that read `state["world"]`); codex should pick
A unless A is impossible.

### 4.2 Permanent regression guard

Per master 2026-06-08 directive:

> 另外这次测试要加一个回归断言：
> UI start game → resume/running → 等待 N 秒 → world month changes
> OR tick count increases
> 否则以后 pytest 全绿但 game loop 死掉的问题还会再发生。

This guard lives at the **test level** — pytest must catch the bug
class even when the UI path isn't exercised. Existing test suites
(43 focused, 1721 broad) all passed under v1.2.2 because none of them
ran `sim.step()` against a scripted-scenario-active world for more
than a single phase. The bug only surfaces when the dispatch state
carries `world` and the scenario has a side event triggering an effect.

New test file `tests/test_game_loop_tick_regression.py`:

**Positive**
- `test_scripted_scenario_apply_effects_does_not_pickle_world` — load
  a minimal scenario with a side event that fires unconditionally with
  empty effects; build dispatch state including `world`; call
  `apply_effects(state, [...])`; assert no exception.
- `test_sim_step_advances_month_with_scripted_scenario` — start a
  liuchao world (or fixture equivalent), call `await sim.step()` N
  times, assert `world.month_stamp` advances by N. Catches the
  silent-failure pattern even when the exception is swallowed.
- `test_game_loop_logs_no_pickle_error` — use `caplog` (Python
  logging) to assert no `cannot pickle` substring during N
  iterations of sim.step on a scripted-scenario world.

**Negative (Layer 5)**
- `test_apply_effects_rolls_back_state_on_handler_error` — confirm
  rollback semantics still work: invoke an effect that raises mid-
  loop, assert `state["npcs"]` (or whichever mutated key) is restored
  to its pre-call value.

These tests pin the contract: a scripted scenario can survive sim.step
without pickle errors, AND the rollback still restores mutated state.

## 5. Scope discipline (what NOT to change)

- No schema change
- No `scenario.json` / preset / mod_platform touch
- No new tests in v1.0.1 / v1.1 / v1.2 / v1.2.1 / v1.2.2 files
- No reformatting of `effect_applier.py` outside the patched function
- No bisect-helper script committed (it's a one-off Hassan diagnostic
  tool at `tools/bisect_game_loop.sh`; can stay in working tree as a
  trace artifact or be deleted before merge — codex's choice but
  recommend deleting)
- No `_build_dispatch_state` change — the original design with
  `state["world"] = world` is correct as an API choice; the bug is
  the over-broad `copy.deepcopy` in `apply_effects`

## 6. Acceptance criteria (codex: PR ready when all hold)

- [ ] `apply_effects` no longer raises `cannot pickle ...` when state
  carries a non-picklable reference (world / sqlite Connection)
- [ ] `apply_effects` rollback semantics preserved: on exception,
  mutated scenario keys revert to pre-call values
- [ ] 4 new tests in `tests/test_game_loop_tick_regression.py` —
  3 positive + 1 rollback negative — all green
- [ ] All 43 v1.2 focused tests still green
- [ ] All 1721 v1.0/v1.1/v1.2 broad tests still green (same 4 pre-
  existing failures: 3 sect-related Stage 2b + 1 environmental port
  binding)
- [ ] `bash tools/bisect_game_loop.sh` against HEAD exits 0 (GOOD)
- [ ] Playwright UI playthrough script (`tools/v1.2.2_playwright_play.js`)
  with a fresh `--scenario=liuchao` reaches month_ticks ≥ 1 within 5
  minutes of init complete (this is the master-mandated player-flow
  regression — Hassan reruns at verification time)

## 7. Codex dispatch hints

Stack order inside this PR:
1. Read this spec end-to-end.
2. Read `src/scenario/effect_applier.py` apply_effects + the imports.
3. Run the existing apply_effects-aware tests if any exist (grep `apply_effects` in `tests/`) — establish the current contract before changing implementation.
4. Implement fix path A in `effect_applier.py` only.
5. Write 4 regression tests in `tests/test_game_loop_tick_regression.py`. For the sim.step tests, follow the fixture style used in `tests/test_scenario_generation_profile.py` and `tests/test_generation_source_control.py` (they already init worlds against /tmp data dirs without LLM).
6. Run focused: `.venv/bin/pytest tests/test_game_loop_tick_regression.py tests/test_sects_pool_warning.py tests/test_generation_source_control.py tests/test_scenario_generation_profile.py tests/test_scenario_avatar_fallback_position.py tests/test_mod_platform.py -v` — expect **47 passed** (4 new + 43 existing).
7. Run broad pytest: `.venv/bin/pytest tests/` — expect 1725 passed / 4 pre-existing failed / 2 skipped.

**Commit + push**: codex sandbox cannot write `.git/index.lock`. Leave changes in working tree on `fix/game-loop-pickle-v1.2.3`. Hassan commits + pushes + ff-merges + tags `v1.2.3-game-loop-fix`.

**Report back with**:
- Files changed (exactly 2: `src/scenario/effect_applier.py` + new test file)
- The exact `ROLLBACK_KEYS` set you chose, with one-line rationale for any key beyond §3's list
- 4-test pass count + per-test names
- Broad pytest count (must match v1.2.2 baseline + 4 new green)
- Sample of the regression test that catches sim.step silent-failure (paste 5-10 lines so master can review the contract)
- Anything surprising — like if a downstream caller actually does rely on `before = copy.deepcopy(state)` semantics in a way the spec didn't anticipate

Be terse but honest. Hassan reviews diff and reruns Playwright player flow before tag.

## 8. Out of scope (deferred)

- Refactoring `_build_dispatch_state` to stop embedding `world`
- Generic "pickling-safe World" infrastructure (would touch save/load)
- Wider audit of other `copy.deepcopy(state)` calls in the codebase
  (codex may grep and flag findings, but do NOT change them)
- Game-loop pickle-error → user-facing alert (UI surfacing of game-
  loop errors)
- Auto-save behavior under scripted scenarios
