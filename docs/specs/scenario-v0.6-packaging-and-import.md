# v0.6 Spec — Scenario Packaging & Import

Date: 2026-06-03
Author: Hassan
Status: **Ready for codex implementation** (御主 22:52 SGT 拍全部按推荐 Q1-Q9 + 4 sub-Qs)
Branch: `feat/scenario-engine-v0.6` (branched off v0.5 HEAD `e6bcfc44`)
Predecessor: v0.5 ready-to-PR (#4 → milestone-C)

## Goal

Player can import their own Scenario as a file/folder, the game validates it, and the player gets a managed list of installed scenarios (with install/remove/enable/disable controls).

Today (v0.5): registry scans `config/scenarios/` only; user-installed scenarios out of scope.
After v0.6: player drops a `.zip` of a scenario, server validates + extracts to `$CWS_DATA_DIR/scenarios/`, registry scans both bundled + user-installed; UI shows manage controls.

## Scope (3 deliverables per master's roadmap)

### 1. Scenario Package format
- Define what a "scenario package" looks like on disk (single .zip? folder? .scenario tarball?)
- Document the package contents requirement

### 2. Import UI + backend
- POST `/api/v1/command/scenario/import` endpoint accepts upload
- Server validates + extracts to user data dir
- Frontend "Import Scenario" button + drag-drop + file picker

### 3. Installed Scenario Management
- UI to Install / Remove / Enable / Disable installed scenarios
- "Disabled" semantics in registry (hide from picker)
- Bundled scenarios are read-only (cannot remove or disable from UI)

### Out of scope (explicit deferral)
- ❌ Online market / community share / repository download (v0.9)
- ❌ Auto-update (v0.9)
- ❌ Scenario authoring wizard (v0.7)
- ❌ Runtime activate/deactivate of active scenario (v0.8)
- ❌ Preset bundling inside scenario packages (v0.7 or v1.0 mod platform)

## Decision Matrix (御主 2026-06-03 22:52 SGT 拍全部按推荐)

| Q | 决策 |
|---|---|
| Q1 | (a) `.zip` only — universal browser support, stdlib zipfile |
| Q2a | (b) 包不带 preset；preset_id 必须 ref 已存在 preset (留 v0.7+) |
| Q3 | install path = `$CWS_DATA_DIR/scenarios/<id>/` |
| Q3a | (b) scenario_id 与 bundled 同名直接 reject |
| Q4 | mandatory 8 项 hard reject + 警告 2 项 |
| Q4a | (a) 深度验证 preset realm/sect/persona/goldfinger ref |
| Q5 | (b) 用户自己 install 同名 → modal 提示 overwrite/rename/cancel |
| Q6 | (b) 复用 ScenarioBrowserModal 加 inline manage actions |
| Q7 | disabled = hide from picker，manager 仍可见 |
| Q7a | (b) disable 也适用 bundled（只藏不删，bundled 文件永远 read-only）|
| Q8 | (c) Import button + drag-drop zone 都做 |
| Q9 | POST `/api/v1/command/scenario/import` multipart，10MB cap |
| Q9a | (a) 同步（包小，延迟可忽略）|

---

## Original 9 Design Q's (for context — decisions above)

### Q1. Package format support
- (a) `.zip` only — universal browser support, single file drag-drop, stdlib `zipfile`
- (b) Folder drop only — raw, requires dir picker
- (c) `.zip` + folder both
- (d) Custom `.scenario` extension (tarball-like) — bespoke

Recommend **(a) .zip only** for v0.6. Folder/`.scenario` can be added later if user feedback demands.

### Q2. Package contents requirement
- v0.6 minimum package = zip containing `<scenario_id>/scenario.json` + `<scenario_id>/timeline.json`. preset_id MUST reference an EXISTING preset (bundled or already-installed). If preset is missing → import fails.
- Q2a: should the package be allowed to **also include** its own preset folder, that gets installed to `$CWS_DATA_DIR/presets/<preset_id>/`?
  - (a) Yes, supported in v0.6 (more flexible, slightly larger import)
  - (b) No, leave preset bundling to v0.7/v1.0 (simpler v0.6, but importing a fully-custom scenario requires user to manually install preset first — friction)
  - Recommend **(b)** for v0.6 simplicity. Document the limitation clearly in the import UX.

### Q3. Install location
- User-installed scenarios live in `$CWS_DATA_DIR/scenarios/<scenario_id>/`
- Bundled scenarios stay at `config/scenarios/<scenario_id>/` (repo-tracked, never written by import)
- v0.5 registry scans only `config/scenarios/`. v0.6 extends scanner to ALSO scan `$CWS_DATA_DIR/scenarios/`.
- Q3a: which directory wins on **scenario_id collision** between bundled and user-installed?
  - (a) Bundled wins, user-installed silently shadowed (warning logged)
  - (b) Import rejected if scenario_id collides with bundled
  - Recommend **(b)** — explicit user feedback better than silent shadow.

### Q4. Validation strictness
- Mandatory checks (reject on fail):
  - Valid zip / unzippable
  - Contains `<scenario_id>/scenario.json` at expected path
  - `scenario.json` parses as JSON
  - `scenario.json` has required fields (`schema_version`, `scenario_id`, `title`, `version`, `world_preset.preset_id`, `initial_state`)
  - `scenario_id` matches the folder name in the zip
  - `world_preset.preset_id` references an existing preset (bundled or installed)
  - timeline.json present and valid per schema v0.1 or v0.2
- Optional/warn (don't fail import, log warning):
  - Extra unknown top-level fields in scenario.json (forward-compat hint)
  - Missing optional metadata (tags, cover_image, author)
- Q4a: dependency validation depth — for v0.6, do we validate that referenced realm_ids / sect_ids / persona_keys / goldfinger_keys exist in the referenced preset?
  - (a) Yes, deep validation (catch authoring bugs at import time, reject before disk write)
  - (b) No, only structural validation — let runtime catch ref errors when scenario loads
  - Recommend **(a)** — better UX (import-time feedback beats runtime crash).

### Q5. Conflict handling on import
- Imported scenario_id matches an EXISTING user-installed scenario_id (not bundled — that's Q3a).
- (a) Reject import (require user to remove old before importing new)
- (b) Prompt user "overwrite / rename / cancel" via modal
- (c) Auto-rename with .1 .2 suffix
- Recommend **(b)** — UX-friendly, makes intent explicit.

### Q6. Management UI placement
- (a) Add a new "Scenario Manager" tab to system menu showing installed list + Install/Remove/Enable/Disable buttons (separate from ScenarioBrowserModal)
- (b) Extend ScenarioBrowserModal (v0.5) to show manage actions inline (each scenario row gets buttons depending on type: bundled = no buttons; installed = Remove + Enable/Disable toggle)
- Recommend **(b)** — reuse v0.5 modal, less UI churn. Add an "Import…" button to the modal as the import entry point.

### Q7. Enable/Disable semantics
- Disabled scenario:
  - Still on disk
  - HIDDEN from the scenario picker dropdown in GameStartPanel
  - Visible in the manager (toggleable)
- Q7a: Does "disable" apply to bundled scenarios too?
  - (a) No — bundled always enabled (`Disable` button greyed for bundled)
  - (b) Yes — user can hide bundled scenarios from their own picker
  - Recommend **(b)** for player control. Bundled is read-only in terms of file ops, but enable/disable status is user-toggleable.
- The enabled/disabled state lives in `$CWS_DATA_DIR/scenarios_state.json` (or similar single-file). Scanner reads this when listing scenarios for the API.

### Q8. Import UX entry point
- (a) "Import Scenario" button on ScenarioBrowserModal that opens file picker
- (b) Drag-drop zone overlay on ScenarioBrowserModal (drop .zip anywhere on modal)
- (c) Both (a) + (b)
- Recommend **(c)** — button is discoverable, drag-drop is faster for power users.

### Q9. Backend import endpoint shape
- POST `/api/v1/command/scenario/import`
- multipart/form-data with a single file field
- Response: `{ok: bool, data: {scenario_id, name, version, ...} | {error: ...}}`
- Maximum file size? — recommend cap at 10 MB for v0.6 (scenarios are tiny text data; if larger, suspect malformed input)
- Q9a: synchronous or async response?
  - (a) Synchronous — validate + extract in the request handler, respond after done. Simple, blocks ≤ 1s for typical scenarios.
  - (b) Async with import-progress polling
  - Recommend **(a)** synchronous for v0.6 — packages are small, latency negligible.

## Implementation contract (PENDING Q sign-off)

### Backend
- `src/server/services/scenario_import.py` (new) — handles import: receive bytes → validate zip → extract to `$CWS_DATA_DIR/scenarios/` → run validation suite → return DTO
- `src/server/services/scenario_state.py` (new) — manages `scenarios_state.json` (enabled/disabled per scenario_id)
- `src/server/api/public_v1/command.py` — add `POST /api/v1/command/scenario/import` (multipart) + `POST /api/v1/command/scenario/remove` + `POST /api/v1/command/scenario/set-enabled`
- `src/server/services/scenario_registry.py` (v0.5) — extend scanner to ALSO scan `$CWS_DATA_DIR/scenarios/`; merge with bundled; filter by `enabled` flag from scenario_state.
- Validation logic lives in `src/scenario/scenario_loader.py` extended with `validate_scenario_dir(path) -> ValidationResult`; reused for import-time and load-time.

### Frontend
- `web/src/api/modules/scenario.ts` — add `importScenario(file)` / `removeScenario(scenario_id)` / `setScenarioEnabled(scenario_id, enabled)`
- `web/src/stores/scenario.ts` — extend with manage actions + invalidation on import/remove
- `web/src/components/game/panels/system/ScenarioBrowserModal.vue` — extend with:
  - "Import…" button → file picker
  - Drag-drop zone overlay
  - Per-row Remove button (user-installed only) + Enable/Disable toggle
  - Source badge: "Bundled" vs "Installed"
- `web/src/types/api.ts` — add ImportResult / ScenarioStateUpdate DTOs

### Tests
- Backend (≥6 new in `tests/test_scenario_import.py`):
  1. Import valid zip → file extracted + scenario shows in registry
  2. Import zip with bad scenario.json → 400 with clear error
  3. Import with missing required field → 400
  4. Import collision with bundled → 400
  5. Remove user-installed scenario → removed from registry; bundled scenario remove rejected
  6. Set enabled=false → scenario hidden from picker but still in manager
- Frontend vitest (≥4 new):
  1. ScenarioBrowserModal renders Import button
  2. ScenarioBrowserModal renders Remove button only for user-installed
  3. Importing valid zip via picker calls API and shows toast
  4. Disabled scenarios show toggle in disabled state

### ADRs
- `docs/adr/ADR-012-scenario-packaging.md` — package format choice (.zip), contents requirement (scenario.json + timeline.json only, no preset bundling in v0.6)
- `docs/adr/ADR-013-scenario-import-validation.md` — validation strictness (deep for v0.6), conflict handling (modal prompt for collision), enable/disable semantics, security considerations (zip-bomb / path traversal protection)

## Security considerations (call out for ADR-013)

- **Zip-bomb protection**: cap uncompressed total size at 100x compressed size + absolute max 100 MB.
- **Path traversal**: reject zips where any entry resolves outside `<scenario_id>/`.
- **Symlink rejection**: zips containing symlinks must be rejected.
- **JSON parsing**: use safe JSON loader; reject if any field is unexpected type (e.g. expected dict got list).

## Acceptance criteria (locked after Q sign-off)

To be populated post Q1-Q9 sign-off. Skeleton:

1. POST `/api/v1/command/scenario/import` with a valid liuchao-like .zip succeeds; file lands in `$CWS_DATA_DIR/scenarios/<scenario_id>/`; subsequent `/api/v1/query/scenarios` includes it
2. Import of malformed/missing/colliding zip rejected with descriptive error
3. Frontend ScenarioBrowserModal shows Import button + drag-drop; valid drop succeeds and refreshes list
4. User-installed scenario has Remove + Enable/Disable controls; bundled doesn't have Remove
5. Disabled scenario hidden from picker but visible in manager
6. Zip-bomb / path-traversal / symlink attacks rejected
7. Backend pytest 137 → ≥ 143 (+6). Frontend vitest 559 → ≥ 563 (+4). Full suite 1645 → ≥ 1651.
8. ADR-012 + ADR-013 land.

## Commit grouping (estimated)

4-5 commits on `feat/scenario-engine-v0.6`:
1. backend import service + scenario_state + endpoint
2. frontend store/api/modal extension
3. registry merge bundled+installed + state filter
4. tests (backend + frontend)
5. ADRs + spec doc updates

---

## What I'm waiting for from master

9 design Q's answered. After sign-off:
1. Fold Q decisions into spec, commit
2. Dispatch codex
3. Hassan verify + 4-5 commits + PR #5 → v0.5 + tag `v0.6-scenario-packaging` + dashboard update + archive
4. Continue to v0.7 spec drafting (per 22:39 SGT autonomous-to-v1.0 directive)
