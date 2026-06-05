# v0.5 Spec — Scenario Discovery & Selection

Date: 2026-06-03
Author: Hassan
Status: **Ready for codex implementation** (御主 21:21 SGT 拍板 Q1-Q7 全部)
Branch: `feat/scenario-engine-v0.5` (branched off milestone-C HEAD `85954526`)
Predecessor: Milestones A/B/C (v0.2–v0.4) all ready-to-PR

## Goal

Player can **discover, choose, and start a scenario from the UI**, without needing CLI knowledge.

Today (Milestone A-C):
```
$ python src/server/main.py --scenario liuchao
[dev knowledge required]
```

After v0.5:
```
Player opens browser → New Game form → picks 「六朝纪事」 from a scenario list → 开始游戏
```

## Scope (4 deliverables per master's roadmap)

### 1. Scenario Registry (backend)
- Filesystem scanner that enumerates installed scenarios under `config/scenarios/`
- Reads each `scenario.json` and extracts metadata fields
- Exposes via `GET /api/v1/query/scenarios` → list of installed scenarios

### 2. Scenario Metadata schema
- Standardize the metadata block at the top of each `scenario.json`
- Existing liuchao/sanguo `scenario.json` already have most fields; v0.5 codifies the contract

### 3. Scenario Browser (frontend modal)
- Modal showing the list of installed scenarios with name / version / author / description / tags
- Opens from a "Browse Scenarios" link in the New Game form
- Read-only (no install/uninstall — that's v0.6)

### 4. Scenario Picker (UI integration)
- Add `scenario_id` field to the New Game settings form
- Default game flow remains (no scenario = `scenario_id: null` or "default")

## Architectural shift required

**Today**: `ACTIVE_SCENARIO_ID = _read_cli_option("--scenario", None)` is module-level constant set at server boot. Game start uses whatever was bound at boot.

**v0.5 needs**: scenario_id selectable per New Game call. Different new games (within the same server process) might use different scenarios.

This requires moving scenario activation from **boot-time-only** to **per-new-game-call**. The CLI flag becomes a default/pre-fill, not a lock.

This is a real architectural change — not destructive, but worth noting up front. See Q1 below.

## Decision Matrix (御主 2026-06-03 21:21 SGT 拍板)

| Q | 决策 |
|---|---|
| Q1 CLI flag 语义 | **(c)** `--scenario` 保留作默认 pre-fill，UI / new game API 可覆盖 |
| Q2 "默认游戏" 选项 | **(b)** 默认游戏/无 scenario 必须进 picker（保持向后兼容）|
| Q3a `title` 命名 | 后端映射 `title → name` DTO 字段；不批量改现有 scenario.json 文件 |
| Q3b `tags` / `cover_image` | 真 optional，缺失不算 validation fail |
| Q4 registry 扫描范围 | **(a)** v0.5 只扫 bundled `config/scenarios/`；user-installed 留 v0.6 |
| Q5 新游戏 UI 集成点 | **(a)** 集成进现有 `GameStartPanel.vue` 表单 |
| Q6 Scenario Browser 形态 | **(a)** Modal，从 GameStartPanel 的 "Browse" 按钮打开 |
| Q7 mid-game scenario 切换 | 不引入；只允许 new-game / reset / init 时选 scenario（runtime activate 留 v0.8）|

---

## Original 7 Design Q's (for context — decisions above)

### Q1. CLI flag semantics
- (a) `--scenario` remains required at boot; picker reads it as locked. UI just shows what was booted; user cannot change.
- (b) `--scenario` removed entirely; boot is scenario-agnostic; picker always asks user at New Game.
- (c) `--scenario` kept as **default pre-fill** for the picker; user can override at New Game.

Recommend **(c)** — backward-compatible with all existing dev/CI/test invocations + lets UI override.

### Q2. "No scenario / default game" option
- (a) Picker requires a scenario selection; no "default game" option in the UI
- (b) Picker has a "默认游戏 (无 scenario)" option that's selectable; selecting it = pre-Milestone-A behavior (random NPCs, no scenario engine, no scripted events)

Recommend **(b)** — keeps existing players' default-game experience intact.

### Q3. Metadata schema — required vs optional fields

Existing `scenario.json` fields (liuchao + sanguo): `schema_version`, `scenario_id`, `title`, `version`, `author`, `description`, `world_preset`, `world_background`, `initial_state`, ...

For v0.5 registry/browser, we need standardized metadata at the top of `scenario.json`:

| Field | Status | Source | Notes |
|---|---|---|---|
| `scenario_id` | required (existing) | filename or scenario.json | identity |
| `title` (内部叫 "name") | required (existing) | scenario.json | display name. 御主 roadmap 用 `name`; existing files 用 `title`. Q3a: rename or alias? |
| `version` | required (existing) | scenario.json | content version |
| `description` | required (existing) | scenario.json | short summary for browser |
| `author` | recommended (existing) | scenario.json | "Chaldeas" / "User" / etc. |
| `tags` | NEW optional | scenario.json | array of strings: `["历史", "六朝", "南北朝"]` |
| `cover_image` | NEW optional | scenario.json | path to PNG/JPG in scenario folder for browser thumbnail |

**Q3a**: Rename existing `title` → `name` in scenario.json files, or keep `title` and have backend map `title` → `name` in the registry API DTO?

Recommend **keep `title`, map to `name` in DTO** — avoids touching liuchao/sanguo/default scenario.json (less churn).

**Q3b**: Make `tags` and `cover_image` truly optional (no validation failure if missing) for v0.5; document them in the schema doc but don't require them.

Recommend yes (default optional).

### Q4. Registry path scope
- (a) Scan only bundled `config/scenarios/` (cws-fork repo's scenarios folder)
- (b) Scan bundled + user-installed scenarios from `$CWS_DATA_DIR/scenarios/`

User-installed = v0.6 import scope. v0.5 only deals with bundled.

Recommend **(a)** for v0.5.

### Q5. New Game UI integration point
- (a) Add `scenario_id` field to existing `GameStartPanel.vue` form (alongside init_npc_num etc.)
- (b) Pre-step before New Game: a dedicated "Choose Scenario" screen, then the existing form

Recommend **(a)** — fits existing CWS UX patterns; less navigation friction.

### Q6. Scenario Browser placement
- (a) Modal opened from a "Browse Scenarios" button in GameStartPanel.vue
- (b) Full-page route `/scenarios`
- (c) Inline list rendered directly in GameStartPanel.vue (no modal/route)

Recommend **(a)** modal — matches existing CWS modal-heavy panel system.

### Q7. Mid-server scenario switching
- User starts game with scenario A. Mid-game, clicks "New Game" with scenario B selected. What happens?
- Same as today's "new game" UX: confirm dialog → reset world → new game with scenario B injected.
- **v0.5 doesn't add new behavior here** — just routes scenario_id through the existing reset/init flow.

This is NOT runtime activate/deactivate (that's v0.8). v0.5 is per-new-game-call. v0.8 is mid-game-mutate without restarting the world.

Recommend confirm — no new design here.

## Implementation contract (PENDING master sign-off on Q1-Q7)

Assuming master picks Q1=(c), Q2=(b), Q3=(map title→name, optional tags/cover), Q4=(a), Q5=(a), Q6=(a) modal, Q7=(no new behavior):

### Backend
- `src/server/services/scenario_registry.py` — new module. `list_installed_scenarios()` walks `config/scenarios/<id>/scenario.json` and returns metadata DTOs.
- `src/server/api/public_v1/query.py` — add `GET /api/v1/query/scenarios` route returning the registry list.
- `src/server/api/public_v1/command.py` — extend `GameStartRequest` schema to accept `scenario_id: Optional[str]`. When the request includes one, override `ACTIVE_SCENARIO_ID` for that game's lifecycle (i.e., `inject_scenario_into_world` uses the request's scenario_id, not the CLI flag).
- `src/server/main.py` — `ScenarioInjectedWorld` already reads `ACTIVE_SCENARIO`. Adapt to read scenario from runtime context (set per game/start call) with CLI flag as fallback default.

### Frontend
- `web/src/api/modules/scenario.ts` — extend with `fetchInstalledScenarios()` (Milestone B already has `fetchScenarioStatus()` for the active game's scenario status)
- `web/src/stores/scenario.ts` — extend with `installedScenarios` ref
- `web/src/types/api.ts` — `InstalledScenarioMeta` DTO
- `web/src/components/game/panels/system/GameStartPanel.vue` — add scenario selector (dropdown or radio group with "Browse" link)
- `web/src/components/game/panels/ScenarioBrowserModal.vue` — new modal showing the list with title / version / author / description / tags
- `web/src/composables/useScenarioBrowserModal.ts` — open/close + selection callback

### Schema doc
- `docs/specs/scenario-metadata-schema.md` — what fields scenario.json must have, what's optional, with examples

### Tests
- Backend (≥3 new in `tests/test_scenario_registry.py`):
  1. `list_installed_scenarios()` returns liuchao + sanguo + (default if it has scenario.json — verify)
  2. API endpoint returns expected DTO shape
  3. Picker selects sanguo → game starts with sanguo scenario_resolved
- Frontend (≥4 new vitest):
  1. ScenarioBrowserModal renders scenario list
  2. Selection emits scenario_id
  3. GameStartPanel passes scenario_id in start payload
  4. Default option "no scenario" works

### ADRs (≥2 per master roadmap)
- `docs/adr/ADR-010-scenario-metadata.md` — metadata schema decisions (which fields required/optional, naming title vs name, tags/cover convention)
- `docs/adr/ADR-011-scenario-discovery.md` — registry scanning strategy, API design, CLI-flag-as-default semantics, lifecycle (boot-time vs per-new-game)

## Out of scope (explicit deferral)

- ❌ Online download / community share / auto-update (v0.9)
- ❌ Scenario installation from .zip / .scenario folder (v0.6)
- ❌ Schema validation on import (v0.6)
- ❌ Install / Remove / Enable / Disable management UI (v0.6)
- ❌ Scenario creator wizard / templates (v0.7)
- ❌ Runtime activate / deactivate / reload (v0.8)
- ❌ Scenario variables / runtime debug view (v0.8)
- ❌ Per-scenario asset packaging beyond cover_image (v0.7+)

## Acceptance criteria (locked after Q1-Q7 sign-off)

To be populated once master signs off the design Q's. Skeleton:

1. `GET /api/v1/query/scenarios` returns liuchao + sanguo + (default?) with metadata fields populated.
2. Browser modal renders the list, click → scenario detail visible.
3. New Game form has a scenario picker; selecting sanguo + clicking "Start" launches a new game with sanguo data injected.
4. Selecting "Default Game (no scenario)" launches a game with `world.scripted_scenario is None` and random NPCs (pre-Milestone-A behavior).
5. CLI flag `--scenario liuchao` still works, but is now a default pre-fill for the picker rather than a lock.
6. Existing backend pytest 131 + Milestone B vitest 4 don't regress.
7. Full pytest: 1639 baseline + new v0.5 tests; 3 pre-existing failures unchanged.
8. ADR-010 and ADR-011 land.

## Commit grouping (estimated, finalized after Q sign-off)

3-4 commits on `feat/scenario-engine-v0.5`:
1. backend registry + API + game-start request extension
2. frontend store + ScenarioBrowserModal + GameStartPanel picker integration
3. tests + ADR-010 + ADR-011 + schema doc

---

## What I'm waiting for from master

7 design Q's answered. After sign-off:
1. I'll commit this spec (with Q answers folded in)
2. Dispatch codex with focused brief
3. Hassan verify + 4 commits + PR #4 → milestone-C + tag `v0.5-scenario-discovery` + dashboard update + archive
