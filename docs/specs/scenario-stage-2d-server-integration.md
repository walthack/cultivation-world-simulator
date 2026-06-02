# Stage 2d D-d2 Spec — Scenario Layer Injection at Server Boot

Date: 2026-06-02 (rev 2)
Author: Hassan
Status: Ready for codex implementation
Master signoff:
- 2026-06-02 22:12 SGT — Q1–Q6 decision matrix
- 2026-06-02 22:16 SGT — clarification: scenario engine = "**场景注入层（Scenario Layer）**", 向世界提供背景设定 / 时间线脚本 / 关系网络 / 事件触发规则
- 2026-06-02 22:21 SGT — chose path **X**: scripted scenario lives ON `world`, simulator adds a noop-on-empty phase to evaluate it; scenario engine退场 after injection

## Goal

Wire scenario engine as **CWS scenario injection layer**: at server boot under `--scenario <id>`, load the resolved scenario and inject its four assets (background / timeline / relations / event rules) into the freshly created world. After injection the engine has no further runtime presence; CWS's own simulator consumes the injected data via a new noop-on-empty phase that reads from `world`.

Out of D-d2 scope: API入口, scenario state 持久化, multi-scenario switching, second example scenario (D-d1).

## Architectural model (locked at master signoff 22:21 SGT)

```
boot:   CLI --scenario liuchao
          ↓
        scenario_loader.load("liuchao") → ResolvedScenario
          ↓
        inject_scenario_into_world(world, resolved)
          ├── world.scripted_scenario = ScriptedScenarioState(timeline, state={}, triggered_events=set())
          ├── (Stage 2c-1 predicate + placeholder already read state["controlled_avatar"])
          └── future: initial NPCs / relations injection (out of D-d2)
          ↓
        scenario engine module exits the boot critical path
                       — does not own the runtime —

run:    Simulator.step()
          phase 12 passive_effects
          phase 12.5 scripted_scenario_tick(world, ctx)   ← reads world.scripted_scenario, noop if None
          phase 13 random minor events
          ...

roleplay:
        start_roleplay / stop_roleplay / mid-session switches
          ↓
        write world.scripted_scenario.state["controlled_avatar"]
```

Key change from rev 1: **scenario state lives on `world`, not `runtime`**. The engine is data + a stateless evaluator; the world owns the live state.

## Decision matrix

| Q | 决策 | Source |
|---|---|---|
| Q1 hook 位置 | (a) 新增 phase 12.5「scripted scenario tick」, 在 passive_effects 之后、autonomous_custom_creation 之前 | 22:12 SGT |
| Q2 API 入口 | (a) D-d2 只做 CLI flag, 不做 activate API | 22:12 SGT |
| Q3 无 scenario 兼容 | `world.scripted_scenario is None` 时 phase 12.5 直接 return [] | 22:12 SGT |
| Q4 roleplay 桥 | start / mid-session switch / stop 三个写 `controlled_avatar_id` 的位置都 sync 到 `world.scripted_scenario.state["controlled_avatar"]` | 22:12 SGT |
| Q5 state 持久化 | (b) D-d2 不做, 留 v0.3 | 22:12 SGT |
| Q6 多 scenario 切换 | 不适用 (Q2 = CLI-only) | 22:12 SGT |
| **X vs Y 评估器宿主** | **X**: data on world, phase reads world field; scenario engine 注入后退场 | 22:21 SGT |

## Scope

### 1. CLI flag → injection

`src/server/main.py:198`:
```python
ACTIVE_SCENARIO_ID = _read_cli_option("--scenario", None)
```
Currently dead. Wire it:

- During world creation (the point where `World(...)` is instantiated and the runtime starts), if `ACTIVE_SCENARIO_ID is not None`, call `src.scenario.scenario_loader.load(ACTIVE_SCENARIO_ID)`.
- Call a new injection helper (proposed: `src/scenario/injector.py::inject_scenario_into_world(world, resolved)`) that:
  - Initializes `world.scripted_scenario` as a `ScriptedScenarioState` dataclass (new type below)
  - Future iterations will also inject avatars / relations from `resolved.scenario` (out of D-d2 scope — explicit follow-up)
- `--scenario foo` referencing a non-existent scenario_id → `scenario_loader.load` raises → server fails to boot. Do NOT silently fallback.
- No flag → `world.scripted_scenario = None`. All downstream code branches on that.

### 2. New types: `ScriptedScenarioState` on `World`

Add to `src/scenario/state.py` (new module, keeps scenario types together):

```python
@dataclass
class ScriptedScenarioState:
    scenario_id: str
    timeline: list[dict]              # the resolved scenario's event list
    state: dict[str, Any] = field(default_factory=dict)  # mutable runtime state
    triggered_events: set[str] = field(default_factory=set)  # event ids already fired
```

Add to `src/classes/core/world.py`:
```python
scripted_scenario: Optional[ScriptedScenarioState] = None
```

Notes:
- `state["controlled_avatar"]` is the only key Stage 2c-1 already reads (predicate + placeholder).
- `triggered_events` prevents the same event firing twice across months.
- Persistence留 v0.3 — for D-d2 the field is in-memory only; save/load skips it.

### 3. phase 12.5 — scripted scenario tick

Create `src/sim/simulator_engine/phases/scripted_scenario.py`:
```python
async def phase_scripted_scenario_tick(world, ctx) -> list[Event]:
    sc = getattr(world, "scripted_scenario", None)
    if sc is None:
        return []
    # invoke the existing dispatcher / condition_evaluator / effect_applier
    # against sc.timeline + sc.state + sc.triggered_events
    # using current year/month from ctx (or world.time)
    # return dispatched events to be added to ctx.events
```

Wire into `src/sim/simulator_engine/simulator.py` step() between phase 12 and phase 13:
```python
# 12.5 Scripted scenario tick
ctx.add_events(await scripted_scenario_phase.phase_scripted_scenario_tick(self.world, ctx))
```

The phase MUST be a noop (return []) when scripted_scenario is None — this guarantees zero behavior change for the default game (no `--scenario` flag).

### 4. roleplay bridge

`src/server/services/roleplay_service.py` has multiple writers of `session["controlled_avatar_id"]` (around lines 184 / 210 / 248 / 423 / 455 / 469 / 471 — verify via grep, line numbers may shift).

Add a helper:
```python
def _sync_scripted_scenario_controlled_avatar(runtime, avatar_id: str | None) -> None:
    world = getattr(runtime, "world", None)
    if world is None:
        return
    sc = getattr(world, "scripted_scenario", None)
    if sc is None:
        return
    if avatar_id is None:
        sc.state.pop("controlled_avatar", None)
    else:
        sc.state["controlled_avatar"] = avatar_id
```

Call sites that must sync:
- `start_roleplay(runtime, avatar_id)` — after writing session, call sync with avatar_id
- `stop_roleplay(runtime, avatar_id)` — after clearing session, call sync with `None`
- `begin_roleplay_choice` / `begin_roleplay_conversation` / `finish_roleplay_choice_wait` — any mid-session writes that change controlled_avatar_id

### 5. No-scenario compatibility

- `python src/server/main.py --dev` (no flag) → `world.scripted_scenario = None`, phase 12.5 returns [], roleplay sync is noop. Identical behavior to pre-D-d2.
- Full pytest (1609 passing / 3 pre-existing failed) must stay at the same numbers. The 3 pre-existing failures in `tests/test_game_init_integration.py` are untouchable, out of scope.

## Files to touch

New:
- `src/scenario/state.py` — `ScriptedScenarioState` dataclass
- `src/scenario/injector.py` — `inject_scenario_into_world(world, resolved)` helper
- `src/sim/simulator_engine/phases/scripted_scenario.py` — phase implementation
- `tests/test_scenario_d2d_server_integration.py` — boot + phase + roleplay E2E
- `docs/adr/ADR-006-scenario-stage-2d-server-integration.md` — codex writes

Modified:
- `src/classes/core/world.py` — add `scripted_scenario: Optional[ScriptedScenarioState] = None` field; ensure save/load currently ignores it (留 v0.3 持久化)
- `src/server/main.py` — consume `ACTIVE_SCENARIO_ID` during bootstrap, call injector with the freshly created world
- `src/sim/simulator_engine/simulator.py` — insert phase 12.5 call between step 12 and step 13
- `src/sim/simulator_engine/phases/__init__.py` — export the new phase (if registry pattern exists)
- `src/server/services/roleplay_service.py` — add `_sync_scripted_scenario_controlled_avatar` helper + 3 call sites

Untouched (forbidden):
- `.venv/` (last codex pass clobbered it — do NOT run uv/pip)
- `tests/test_game_init_integration.py` (pre-existing failures)
- API surface (no new endpoints)
- save/load code (state持久化 留 v0.3)

## Acceptance criteria

1. `python src/server/main.py --dev --scenario liuchao` boots cleanly; immediately after boot, `world.scripted_scenario` is a `ScriptedScenarioState` with `scenario_id="liuchao"` and `timeline` non-empty.
2. `python src/server/main.py --dev` boots; `world.scripted_scenario is None`. Running any number of simulator steps produces no scenario-engine events.
3. With `--scenario liuchao` active, one `await simulator.step()` advances time to year 1 month 1 and dispatches `liuchao-opening`. `world.scripted_scenario.triggered_events` includes `liuchao-opening`.
4. With `--scenario liuchao` + `start_roleplay(avatar_id="cheng-zongyang")`, advancing to year 1 month 2 dispatches `cheng-zongyang-arrives-at-linan-gate` only; `wang-zhe-arrives-at-linan-gate` and `xiao-zi-arrives-at-linan-gate` do NOT fire (their controlled_avatar_is predicate fails).
5. After `start_roleplay(avatar_id="wang-zhe")` in a freshly booted server, advancing to year 1 month 2 dispatches `wang-zhe-arrives-at-linan-gate`. Proves the roleplay bridge writes scripted_scenario.state correctly.
6. `--scenario does-not-exist` causes server boot to raise and exit non-zero.
7. Scenario subset pytest: 109 → ≥ 113 (D-d2 adds ≥ 4 server integration tests). No regressions.
8. Full pytest: 1609 passing remains 1609; 3 pre-existing failures unchanged.
9. ADR-006 lands at `docs/adr/`, explains:
   - phase 12.5 position choice
   - X-vs-Y decision: data on world, evaluator phase reads world
   - no-scenario noop strategy
   - roleplay 3-point bridge rationale
   - state persistence deferral

## Out of scope (D-d2)

- Initial NPC / relation injection from scenario (currently scenario.json has `initial_state.avatars`; D-d2 only injects timeline + state). Avatar / relation injection is a follow-up — adds value but Q5 says keep D-d2 lean.
- POST `/api/v1/command/scenario/activate` (Q2 = no)
- Save/load `scripted_scenario` (Q5 = no)
- Multi-scenario switch (Q6 N/A)
- D-d1 second example scenario (next task, separate dispatch)

## 工程量预估

~3-4 days of codex implementation (including ADR + tests). Hassan handles git commits if `.git/index.lock` blocks codex.

---

## Revision history

- **rev 1** (2026-06-02 22:12 SGT): initial spec assuming scenario state lives on runtime, scenario engine owns its dispatcher.
- **rev 2** (2026-06-02 22:23 SGT, this version): master clarified scenario engine = injection layer; state moved to `world.scripted_scenario`; engine退场 after injection; phase reads from world.
