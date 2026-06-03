# Stage 2d D-d2 Bugfix Spec — Scenario start_year/month Injection

Date: 2026-06-03
Author: Hassan
Status: Ready for codex implementation
Master signoff: 2026-06-03 11:36 SGT — Option A, 5 acceptance criteria locked

## Bug summary

D-d2 wired scenario engine into live runtime (phase 12.5 ✓, CLI flag ✓, injection ✓), but the world's start_year is still hardcoded to `static/config.yml :: world.start_year = 100`. Active scenarios' `initial_state.year / month` are silently ignored. With dispatcher requiring exact year/month match (`event_dispatcher.py:31`), liuchao timeline events (`trigger.year = 1/2`) and sanguo timeline events (`trigger.year = 208`) are unreachable in live play.

Pytest e2e tests bypass the bug by manually pinning `state["world"]["year"] = 1` before driving the dispatcher (`tests/test_scenario_e2e_liuchao.py:72`). The live `Simulator.step()` path has no such injection, so scenario engine ships engine-wired but data-unreachable.

## Decision (御主 lock)

**Option A**: scenario `initial_state.year/month` override CWS default `start_year/start_month` when a scenario is active.

Explicitly NOT chosen:
- ❌ Retarget timeline data to year 100 (let data follow CWS default)
- ❌ Change dispatcher trigger semantics from `==` to `>=`
- ❌ Inject scenario avatars into `world.avatar_manager` (still out of scope per D-d2 spec)

## Acceptance criteria (御主 dictate)

1. Starting with `--scenario liuchao` initializes `world.month_stamp` to scenario `initial_state.year=1, month=1`.
2. Starting with `--scenario sanguo` initializes `world.month_stamp` to scenario `initial_state.year=208, month=1`.
3. Existing no-scenario start still uses `static/config.yml` default `start_year=100`, `start_month=1`.
4. Dispatcher exact-match tests (existing `event_dispatcher.py` contract) still pass — do not change `==` semantics.
5. **Add a regression test that fails BEFORE this fix**: live/init-flow path with scenario active must NOT require manually pinning `state["world"]["year"] = 1`. Use the real `inject_scenario_into_world` + a `World` built via init flow (or stub equivalent), then verify dispatching at year 1 month 1 fires `liuchao-opening` without any manual state mutation.

## Where the bug lives

`src/server/init_flow.py:238-243`:
```python
start_year = getattr(config.world, "start_year", 100)
world = world_cls.create_with_db(
    map=game_map,
    month_stamp=create_month_stamp(year_cls(start_year), month_enum.JANUARY),
    events_db_path=events_db_path,
    start_year=start_year,
)
```

`world_cls` here is `ScenarioInjectedWorld` (from `src/server/main.py:204`):
```python
class ScenarioInjectedWorld:
    @classmethod
    def create_with_db(cls, *args, **kwargs):
        world = World.create_with_db(*args, **kwargs)
        if ACTIVE_SCENARIO is not None:
            inject_scenario_into_world(world, ACTIVE_SCENARIO)
        return world
```

The injection happens AFTER `World.create_with_db` runs, but `world.month_stamp` is already set to (start_year=100, January) by then.

## Recommended fix (codex has implementation discretion within these bounds)

Two viable approaches. Codex pick one:

### Approach 1 (preferred) — pre-create-world peek
Modify `ScenarioInjectedWorld.create_with_db` (or wherever `start_year` is resolved) so that when `ACTIVE_SCENARIO` is non-None, the resolved scenario's `initial_state.year` and `initial_state.month` replace the `month_stamp` kwarg AND the `start_year` kwarg BEFORE calling `World.create_with_db`. Don't mutate after.

### Approach 2 — in-injector mutation
Have `inject_scenario_into_world(world, resolved)` read `resolved.scenario["initial_state"]["year"]` and `["month"]`, then mutate `world.month_stamp` to the new value AND update `world.start_year` if that's a separate field. Verify nothing in `World.create_with_db` has already consumed the old value in a way that can't be re-overridden (e.g., events emitted at year 100 that need to be discarded).

**If `world.dynasty.current_emperor = generate_emperor(world.dynasty, int(world.month_stamp))` at `init_flow.py:244` depends on the month_stamp being the FINAL value**, Approach 1 is safer (Approach 2 would require also mutating `dynasty.current_emperor` post-hoc).

## Files expected to touch

- `src/scenario/injector.py` or `src/server/main.py` (the `ScenarioInjectedWorld` wrapper) — implement the override
- `src/scenario/state.py` — likely no change (year/month not tracked on `ScriptedScenarioState`)
- `tests/test_scenario_d2d_server_integration.py` — extend with the regression test
- `docs/adr/ADR-007-scenario-start-time-injection.md` — short ADR documenting Approach 1 vs 2 choice + rationale

## Forbidden scope

- No dispatcher change (exact-match `==` stays)
- No timeline data edits in `config/scenarios/{liuchao,sanguo}/timeline.json`
- No `static/config.yml` change (default keeps year 100)
- No avatar injection into `world.avatar_manager`
- No `.venv/` touches

## Acceptance verification (Hassan runs after codex done)

1. Boot `--scenario liuchao --dev`, hit `/api/v1/query/world/state`, assert `year == 1, month == 1`.
2. Boot `--scenario sanguo --dev`, hit same, assert `year == 208, month == 1`.
3. Boot without `--scenario`, hit same, assert `year == 100, month == 1`.
4. Full pytest: scenario subset green; regression test green.

## Commit grouping

1-2 commits on current branch `feat/scenario-engine-stage-2d`:
- `fix: D-d2 — inject scenario initial_state.year/month into world start_year`
- (optional) `test: D-d2 — regression test for scenario start-time injection`

If `.git/index.lock` blocks, write files and report unstaged — I'll commit.

## Reporting format

```
WROTE (new files):
  <list>
MODIFIED (existing files):
  <list>
APPROACH CHOSEN: 1 or 2 (with one-line rationale)
NEW TEST COUNT: 121 -> <N> (scenario subset)
COMMITS: <sha + subject> | unstaged | blocked
DEVIATIONS FROM SPEC: <list>
```
"PARTIAL — done: X, remaining: Y" if you bail.
