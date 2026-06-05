# v0.8 Spec — Runtime Scenario Control

Date: 2026-06-03
Author: Hassan
Status: **Ready for codex implementation** (御主 2026-06-04 00:25 SGT 拍全部按推荐 + hot-swap 时间锚警告 verbatim)
Branch: `feat/scenario-engine-v0.8` (branched off v0.7 HEAD `4d506399`)
Predecessor: v0.7 ready-to-PR (#6 → v0.6)

## Goal

Three runtime controls on the active scenario:
1. **Activate** — load a new scenario on the LIVE game without server restart
2. **Deactivate** — strip scenario data from a running game (revert to default game flow)
3. **Reload** — re-read scenario from disk to pick up edits (creator workflow)

Plus:
4. **Scenario variables** — generalize the `scripted_scenario.state` dict so scenarios can read/write named variables via effects (today only `controlled_avatar` lives there)
5. **Runtime debug view** — UI panel showing scenario state internals (variables, triggered events, dispatcher diagnostics)

Scope裁剪 per master 21:13 SGT — **save/load persistence already shipped in Milestone C / ADR-009**, NOT redone here. v0.8 builds on top of C's persistence.

## Out of scope (explicit deferral)

- ❌ save/load persistence (Milestone C done)
- ❌ triggered event persistence (Milestone C done)
- ❌ Authoring during runtime (v0.7 wizard is offline-only)
- ❌ Community / share / online (v0.9)
- ❌ Plugin authoring (v1.0 mod platform)

## Decision Matrix (御主 2026-06-04 00:25 SGT 拍全部按推荐)

| Q | 决策 |
|---|---|
| Q1 | (c) 两选 mode：`reset` (默认) + `hot-swap` (power user)，UI 弹 confirm |
| Q2 | (a) hot-swap 不 re-anchor 时间，过去的 trigger 自然 unreachable |
| Q3 | (a) Deactivate 只 strip state，scenario-注入 avatar 保留 |
| Q4 | (a) Reload 保留 state + triggered_events，刷 timeline+metadata 自盘 |
| Q5 | 新 `set_var` effect + `var_equals` predicate，操作 scripted_scenario.state |
| Q5a | vars per-scenario（state），非 per-world（world_flags 保留作跨 scenario）|
| Q6 | (a) ScenarioOverviewModal 加 Debug tab |
| Q7 | state vars + triggered events + 近 50 dispatch log（含失败原因） |
| Q7a | (b) v0.8 不做 force-fire 按钮（read-only debug）|
| Q8 | 4 个 endpoint：activate / deactivate / reload / GET debug |
| Q8a | (b) advanced-mode gate，Settings 加开关默认关 |

### Hot-swap 时间锚警告（御主 verbatim 要求落 ADR-016）

ADR-016 MUST include this exact wording:

> **Hot-swap does not re-anchor time. Events scheduled before the current world time will not fire.**

This warning ALSO appears in:
- Settings "Advanced runtime control" toggle help text
- Activate confirm modal when user selects hot-swap mode
- Backend ScenarioActivateRequest response when mode=hot-swap chosen (returns `warning: "Hot-swap does not re-anchor time..."` field for frontend display)

---

## Original 8 Design Q's (for context — decisions above)

### Q1. Activate mid-game — hot-swap vs reset-and-activate
A game is running with scenario A. User clicks "Activate B" on a running world.

- (a) **Hot-swap**: replace `world.scripted_scenario` with B's data in place. Game continues at current year/month with B's timeline events evaluated forward.
- (b) **Reset & activate**: discard the running game, create fresh world with B (same as v0.5 new-game).
- (c) **Both options offered** via a `mode` parameter on the activate endpoint. UI confirm modal asks which.

Recommend **(c)** — user choice. Default to (b) reset (safer); (a) hot-swap is power-user mode.

### Q2. Hot-swap time-anchor handling
Hot-swap edge case: scenario B has timeline events at `trigger.year=1`, but live world is at `year=105`. New scenario's year-1 events are unreachable.

- (a) Hot-swap takes scenario as-is; year-1 events just won't fire (acceptable, document as known limitation)
- (b) Hot-swap **re-anchors** scenario's timeline to current world year (shift all triggers by `current_year - scenario.initial_state.year`)
- (c) Refuse hot-swap if scenario's earliest trigger is in the past relative to current world year (force user to use reset mode)

Recommend **(a)** for v0.8 — simplest, predictable, documented. (b) would silently mutate scenario data, (c) is too restrictive.

### Q3. Deactivate semantics
- (a) **Strip scenario state only**: set `world.scripted_scenario = None`. Scenario-injected avatars STAY as part of world (already integrated into avatar_manager).
- (b) **Strip scenario state + scenario-injected avatars**: remove the scenario's NPCs from world.avatar_manager too. Risky — those avatars may have already participated in events, have relations, etc.

Recommend **(a)** — preserves world history integrity. Player can manually remove individual avatars via existing CWS UI if needed.

### Q4. Reload behavior on state preservation
Reload = re-read scenario file from disk (creator updated their scenario.json and wants to test).

- (a) Preserve `scripted_scenario.state` AND `triggered_events` (only refresh timeline + metadata from disk)
- (b) Preserve `state` but RESET `triggered_events` (re-fire events from beginning)
- (c) Full reset (state + triggered_events both cleared)

Recommend **(a)** — least surprising. Reload picks up authoring changes; runtime state stays intact. Creator can use "Activate (reset)" if they want a clean re-run.

### Q5. Scenario variables — DSL extension
Today `scripted_scenario.state` is a plain dict; effects can `set_flag` into `world.world_flags` but NOT into `scripted_scenario.state`. v0.8 generalizes:

- Add `set_var` effect: `{type: "set_var", name: str, value: any}` writes to `scripted_scenario.state[name]`
- Add `var_equals` predicate: `{var_equals: {name: str, value: any}}` reads from `scripted_scenario.state[name]`
- Existing `controlled_avatar` keeps working as before (it's just a special variable)

Q5a: scoping — vars live on scripted_scenario.state (per-scenario) or on world.world_flags (per-world)?
- Recommend **per-scenario** (`scripted_scenario.state`) — scenario-defined vars are scenario-scoped, deactivate clears them. world.world_flags reserved for cross-scenario state.

### Q6. Runtime debug view — UI placement
- (a) Add "Debug" tab to existing `ScenarioOverviewModal` (Milestone B's modal)
- (b) Separate `ScenarioDebugModal` opened from a Debug button
- (c) Console-style log overlay (always-visible during gameplay when scenario active)

Recommend **(a)** Add Debug tab to ScenarioOverviewModal. Reuses existing modal; debug is opt-in (open modal to see).

### Q7. Runtime debug view — content
What's IN the debug tab?
- Current `scripted_scenario.state` variables (key: value table, live-refresh)
- Triggered events list (already in v0.3 visibility, link/share)
- Recent dispatch attempts (last N: timestamp + event_id + reason if not fired — e.g. "condition failed: var_equals foo expected bar got baz")
- "Force-fire" button per untriggered event for debug-time testing?

Q7a: Force-fire button — too dangerous for accidental use?
- (a) Yes include with confirm modal
- (b) No, debug view is read-only

Recommend **(b)** read-only for v0.8. Force-fire = creator workflow shortcut, deferable.

### Q8. Backend API endpoints
- `POST /api/v1/command/scenario/activate` body `{scenario_id: str, mode: "reset" | "hot-swap"}`
- `POST /api/v1/command/scenario/deactivate`
- `POST /api/v1/command/scenario/reload`
- `GET /api/v1/query/scenario/debug` returns runtime state for debug view

Authentication / authorization: all these are local-only, no auth in CWS today; existing endpoints have no guard either. v0.8 follows the pattern.

Q8a: Should activate/deactivate/reload be guarded by an "advanced mode" toggle in settings (so default players don't accidentally break their game)?
- (a) Always available (consistent with simple UX)
- (b) Behind an "Advanced runtime control" settings toggle

Recommend **(b)** — these are power-user features and deactivate especially is destructive. Off by default; opt-in via Settings.

## Implementation contract (PENDING Q sign-off)

### Backend
- `src/server/services/scenario_runtime.py` (new) — implements activate / deactivate / reload as service functions
- `src/server/services/scenario_debug.py` (new) — assembles debug DTO (state vars + recent dispatch log + triggered list)
- `src/server/api/public_v1/command.py` — 3 new endpoints + 1 query
- `src/scenario/event_dispatcher.py` (extend with dispatch log capture, append-only ring buffer last N=50)
- `src/scenario/condition_evaluator.py` (extend with `var_equals` predicate)
- `src/scenario/effect_applier.py` (extend with `set_var` effect)
- `src/server/runtime/session.py` — extend with `advanced_runtime_control` setting + dispatch log buffer attached to scripted_scenario or runtime

### Frontend
- `web/src/api/modules/scenario.ts` — add activate / deactivate / reload / debug HTTP calls
- `web/src/stores/scenario.ts` — add runtime control actions + debug state polling
- `web/src/components/game/panels/ScenarioOverviewModal.vue` (extend) — add "Debug" tab when advanced mode on; "Activate / Deactivate / Reload" buttons in main view (gated by advanced setting)
- `web/src/components/system-menu/SettingsTab.vue` — add "Advanced runtime control" toggle
- `web/src/types/api.ts` — add RuntimeControlRequest, DebugSnapshot DTOs

### Tests
- Backend (≥7 in `tests/test_scenario_runtime.py`):
  1. Hot-swap: activate(B, mode=hot-swap) on running world → scripted_scenario.scenario_id == B, scripted_scenario.state cleared, world.month_stamp UNCHANGED
  2. Reset: activate(B, mode=reset) → world recreated at scenario B's initial year
  3. Deactivate: scripted_scenario becomes None, scenario-injected avatars STAY in world.avatar_manager (per Q3=a)
  4. Reload preserves state + triggered_events (per Q4=a)
  5. set_var effect writes to scripted_scenario.state
  6. var_equals predicate reads from scripted_scenario.state
  7. /debug query returns expected DTO shape with vars + dispatch log
- Frontend vitest (≥4):
  1. Debug tab renders when advanced mode on, hidden when off
  2. Activate confirmation modal triggered by Activate button
  3. Deactivate confirmation modal triggered
  4. Debug tab shows scripted_scenario.state vars + last-N dispatch attempts

### ADRs
- `docs/adr/ADR-016-runtime-scenario-control.md` — activate/deactivate/reload semantics, hot-swap edge case (Q2=a known limitation), advanced-mode gate
- `docs/adr/ADR-017-scenario-runtime-debugging.md` — debug DTO shape, dispatch log ring buffer, debug tab as part of ScenarioOverviewModal, read-only stance (no force-fire)

## Acceptance criteria (locked after Q sign-off)

To be populated post Q1-Q8 sign-off. Skeleton:

1. POST `/scenario/activate` with `mode=reset` and known scenario_id resets world, applies new scenario at its initial year/month
2. POST `/scenario/activate` with `mode=hot-swap` leaves world.month_stamp untouched, swaps scripted_scenario in place
3. POST `/scenario/deactivate` clears scripted_scenario, keeps avatars
4. POST `/scenario/reload` re-reads timeline from disk, preserves triggered_events
5. `set_var` effect writes to scripted_scenario.state; `var_equals` predicate reads it; both work in `tests/test_scenario_condition_evaluator.py` style tests
6. GET `/scenario/debug` returns vars + recent dispatch attempts + triggered list
7. Frontend Debug tab visible only when advanced mode setting on
8. Activate/Deactivate buttons only visible when advanced mode on
9. Backend pytest 155 → ≥ 162 (+7). Full suite 1663 → ≥ 1670.
10. ADR-016 + ADR-017 land.

## Commit grouping (5-6 commits on `feat/scenario-engine-v0.8`)
1. backend runtime + debug services + 4 endpoints + DSL extensions (set_var, var_equals)
2. dispatcher log ring buffer + session advanced-mode setting
3. frontend store + api + modal extension + Debug tab + Settings toggle
4. tests
5. ADRs

---

## What I'm waiting for from master

8 design Q's answered. After sign-off: fold + commit + dispatch codex.
