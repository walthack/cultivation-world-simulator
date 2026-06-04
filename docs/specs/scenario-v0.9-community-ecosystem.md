# v0.9 Spec — Community Scenario Ecosystem

Date: 2026-06-04
Author: Hassan
Status: **Ready for codex implementation** (御主 2026-06-04 00:46 SGT 拍 Q1-Q9 + 新增 Scenario Fingerprint 功能)
Branch: `feat/scenario-engine-v0.9` (branched off v0.8 HEAD `a679fcd0`)
Predecessor: v0.8 ready-to-PR (#7 → v0.7)

## Goal

Make scenarios shareable. Player can:
- **Export** an installed scenario as a .zip file (reverse of v0.6 import)
- **Version** scenarios with semver-like rules + engine compat
- **Declare dependencies** (presets, assets, libraries) in scenario.json
- **Browse** a local repository organized into tabs: Installed / Downloaded / Updates

Scope-cap: **v0.9 is strictly LOCAL.** No online marketplace, no server, no auto-download. "Sharing" means user drops a .zip somewhere (chat, GitHub, USB stick), recipient places it in their Downloads folder, the UI surfaces it. Marketplace hosting is v1.0+ Mod Platform scope.

## Out of scope (explicit deferral)

- ❌ Online marketplace / community server (deferred — could land in v1.0 as a mod platform extension)
- ❌ Auto-download (no marketplace, no polling)
- ❌ Auth / accounts (no online piece)
- ❌ P2P sync (not on the roadmap)
- ❌ Asset bundling beyond presets (cover_image upload UI still v1.0 mod platform)
- ❌ LLM-assisted authoring (v0.7 done)
- ❌ Runtime activate/deactivate (v0.8 done)

## Decision Matrix (御主 2026-06-04 00:46 SGT 拍全部按推荐 + 新增 Fingerprint)

| Q | 决策 |
|---|---|
| Q1 | (a) 严格本地，不做在线 marketplace stub |
| Q2 | (b) lenient semver |
| Q3a | engine compatibility field optional（legacy 兼容；creator-toolkit 生成时带）|
| Q4a | (a) 仅 preset dependency（scenario-on-scenario 留 v1.0+）|
| Q5a | Downloaded 与 v0.6 Import workflow 分离（Import 直接到 Installed；Downloaded 是独立 "已下载未安装"流）|
| Q6a | Export 只导 scenario 数据，不导 enable/state |
| Q7 | Update 前自动 archive 旧版本到 `$CWS_DATA_DIR/scenarios_archive/<id>/<old_version>/` |
| Q8 | 3 command（export/install-from-download/update）+ 1 query（repository）|
| Q9a | (b) warn-and-confirm modal，不 hard reject |

**关于 Marketplace（御主 21:47 SGT 说明）**：不塞进 v0.9，原因不是技术而是产品边界。v0.9 结束时用户已可 Create/Export/Share/Import/Install/Update/Enable/Disable 完整闭环。Marketplace 留 v1.0 Mod Platform。

---

## NEW: Scenario Fingerprint（御主 00:46 SGT 加新功能）

### 动机（御主原话）
> 未来：Export ↓ Discord ↓ GitHub ↓ USB 会出现：liuchao.zip / liuchao-final.zip / liuchao-final-final.zip。有 fingerprint 后 same package? / modified package? / corrupted package? 都能快速判断。

### Fingerprint 规格

**字段**：`scenario.fingerprint` 在 scenario.json metadata 顶层。形如 `"sha256:abc123..."`。

**内容（Hassan 定）**：content-based hash 覆盖 scenario.json + timeline.json 的 canonical 序列化（sorted keys, 稳定 byte ordering）。**排除 fingerprint 字段自己**（不能 self-include）。

**生成时机**：
- **On Export**：系统计算 fingerprint，**embed 进 .zip 内的 scenario.json**。原 installed 副本 scenario.json **不被修改**（保持用户文件 clean）。
- **On Install / Import**：系统按内容重新计算 fingerprint，与 metadata 里的 `fingerprint` 字段对比：
  - 字段存在 + 匹配 → 显示 "Verified ✓"
  - 字段存在 + 不匹配 → 显示 "Modified ⚠" warning（package 被改过）
  - 字段不存在 → 显示 "Unsigned"（legacy 包或本地手写）
- **On Repository Listing**：每个 card 显示 fingerprint 前 8 位 + 验证状态 icon

**对应"3 questions"判断**：
- **Same package?** → fingerprint 一致
- **Modified package?** → scenario_id 同但 fingerprint 不同
- **Corrupted package?** → fingerprint 字段在但内容不匹配（含义 fingerprint 应该被信任，实际数据不一致 = 损坏或篡改）

### Implementation

- `src/scenario/fingerprint.py` (new) — `compute_scenario_fingerprint(scenario_data, timeline_data) -> str` 返回 `"sha256:" + hex_hash`
- Export 流程在写入 .zip 前对 scenario.json deep-copy + 注入 `fingerprint` 字段
- Import 流程在 metadata 解析后重新计算，对比，结果带进 ImportResult.verification = {"status": "verified"|"modified"|"unsigned", "computed": "...", "claimed": "..."}
- Registry DTO + repository query 都带 `fingerprint` + `verification` 字段

### ADR-018 必含 fingerprint 节
ADR-018 doc 中明确：
- Fingerprint 算法（sha256 over canonical JSON of scenario.json + timeline.json，排除 fingerprint 字段自己）
- 字段路径 + 生成时机（export 时注入 / import 时验证）
- 三态判定语义（verified / modified / unsigned）
- 不修改用户 installed 副本 scenario.json 的设计选择

---

## Original 9 Design Q's (for context — decisions above)

### Q1. Repository scope: local-only vs. minimal online stub
- (a) **Strictly local**: Export + Versioning + Dependency declaration + Repository UI tabs. "Downloaded" tab = scenarios in a `$CWS_DATA_DIR/scenarios_downloads/` folder. No server piece.
- (b) Minimal online stub: define a `/repository` API server-side that's a no-op now, v1.0 extends.

Recommend **(a)** — focused deliverable. Online server == multi-week project; out of v0.9 time budget.

### Q2. Versioning rules
- `scenario.json` already has a `version` field (currently free-form string e.g. "1.0"). Enforce **semver** (X.Y.Z, optional pre-release) for v0.9?
  - (a) Yes, strict semver — reject import if version not semver
  - (b) Yes, lenient — accept any string, but compare semantically when possible
  - (c) No, leave as free-form
- Add a `schema_version` enforcement: scenario_loader already supports 0.1 + 0.2; v0.9 just documents the semantics in ADR-018.

Recommend **(b)** — strict can break legacy; lenient gets the upgrade-detect feature.

### Q3. Engine compatibility declaration
Add `engine` field to scenario.json metadata:
```json
"engine": {
  "schema_version_min": "0.2",
  "cws_version_min": "3.4.0"
}
```
On import: reject if current engine schema_version is below `schema_version_min` OR cws_version < `cws_version_min`.

Q3a: Make `engine` field **required** for new scenarios, OR optional (default = "any")?
  - (a) Required for v0.9+ schema
  - (b) Optional (legacy + creator-toolkit-generated scenarios may omit it; default permissive)

Recommend **(b)** — legacy compat. Document in ADR-018 that v0.9 creator-toolkit emits it; old scenarios without it = "untested compat".

### Q4. Dependency declarations
Add `dependencies` array to scenario.json:
```json
"dependencies": [
  {"type": "preset", "id": "liuchao", "version_req": ">=1.0"},
  {"type": "scenario", "id": "base_dynasty_pack", "version_req": ">=1.2"}
]
```
Q4a: Which types to support in v0.9?
  - (a) `preset` only (covers existing world_preset linkage)
  - (b) `preset` + `scenario` (allow scenario-on-scenario deps — power but complex resolution)
  - (c) `preset` + `scenario` + `asset` (full Q4 set per roadmap "Assets / Presets / Libraries")

Recommend **(a)** for v0.9 — `world_preset.preset_id` already implies a preset dep; v0.9 just formalizes the syntax. Scenario-on-scenario and asset deps complicate resolver too much for one milestone.

### Q5. Repository UI tabs
- Inside `ScenarioBrowserModal` (Milestone B asset), add tab nav at the top:
  - **Installed** — currently active scenarios (bundled + user-installed under `$CWS_DATA_DIR/scenarios/`)
  - **Downloaded** — `.zip` files or extracted folders in `$CWS_DATA_DIR/scenarios_downloads/` (NOT yet installed; user clicks "Install" to move to Installed)
  - **Updates** — list of (installed scenario, newer version available in Downloads) pairs; user clicks "Update" to replace

Q5a: Where do "Downloaded" .zips come from? 
  - User puts them there manually (drag from file explorer)
  - OR: v0.6 import flow stores accepted .zips in Downloads first, user explicitly installs
  - Recommend: v0.6 import flow stays the same (extracts directly to Installed); Downloaded is a SEPARATE workflow for "I have a .zip but haven't installed yet — let me browse it first".

### Q6. Export functionality
- "Export" button on each installed scenario in the Installed tab
- Server packages the scenario dir into a .zip and returns it for download
- Q6a: Include scenario_state.json (enabled flag) in export? Or strictly scenario data?
  - Recommend **scenario data only** (no state). User who imports the .zip gets it as a fresh installed scenario, default enabled.

### Q7. Updates tab detection logic
- When user puts a newer-version .zip in Downloads, the Updates tab shows: `"liuchao 1.0 → 1.1 available"`
- Detection: read installed scenario.json's `version`; for each Downloaded .zip, compare `scenario_id` + `version`. If same id + newer version → Updates list.
- Click "Update": back up old installed dir (e.g. to `incompatible/` per existing CWS pattern), then atomic move new dir into place.

Q7a: Back up old version on update — to where?
  - Recommend `$CWS_DATA_DIR/scenarios_archive/<scenario_id>/<old_version>/` (clean path, easy to inspect)

### Q8. Backend API
- `POST /api/v1/command/scenario/export` body `{scenario_id: str}` → returns .zip blob (binary response)
- `POST /api/v1/command/scenario/install-from-download` body `{download_id: str}` (download_id is filename hash or similar)
- `POST /api/v1/command/scenario/update` body `{installed_scenario_id: str, download_id: str}`
- `GET /api/v1/query/scenario/repository` returns `{installed: [...], downloaded: [...], updates: [...]}` (one query for all 3 tabs)

### Q9. Compatibility check timing
- Compatibility checks (schema_version_min, cws_version_min, dependencies resolution) run:
  - At import time (already v0.6 partial; v0.9 enriches with new fields)
  - At install-from-download time (similar)
  - At update time (new flow)
- If any check fails → reject with descriptive error
- Q9a: warn-only mode? E.g. "scenario claims requires cws 4.0 but you're on 3.4.0; still install?"
  - (a) Strict reject (safe but rigid)
  - (b) Warn-and-confirm modal (user chooses)
  - Recommend **(b)** — author intent honored, user can override knowingly.

## Implementation contract (PENDING Q sign-off)

### Backend
- `src/server/services/scenario_export.py` (new) — packages installed scenario dir into .zip bytes; respects "scenario data only" policy (no state)
- `src/server/services/scenario_repository.py` (new) — assembles `{installed, downloaded, updates}` DTO; reads Downloads folder; computes updates by id+version comparison
- `src/server/services/scenario_compat.py` (new) — schema_version + cws_version + dependency checks; returns CompatResult with pass/warn/fail per criterion
- `src/server/api/public_v1/command.py` — 3 new endpoints (export / install-from-download / update)
- `src/server/api/public_v1/query.py` — `GET /api/v1/query/scenario/repository`
- `src/scenario/scenario_loader.py` — extend metadata schema with optional `engine` + `dependencies` fields; integrate into deep validation
- `src/scenario/scenario_loader.py` — semver helpers if Q2=(a) or (b)
- `config/templates/scenario/*.json` — extend with `engine` + (empty) `dependencies` in each template; document in v0.7 schema doc update

### Frontend
- `web/src/components/game/panels/system/ScenarioBrowserModal.vue` — add Installed/Downloaded/Updates tab nav at top
- `web/src/components/game/panels/system/ScenarioRepositoryTabs.vue` (new) — encapsulates tab content rendering
- Per-card actions: Export (on Installed), Install (on Downloaded), Update (on Updates)
- Compatibility warn-and-confirm modal (Q9a=b)
- `web/src/api/modules/scenario.ts` — extend with new endpoints
- `web/src/types/api.ts` — add Repository DTO, CompatResult DTO

### Tests
- Backend (≥7 in `tests/test_scenario_repository.py`):
  1. `list_repository` returns installed + downloaded + updates correctly
  2. Export endpoint returns valid .zip readable by v0.6 import
  3. Round-trip: export → re-import → registry shows it
  4. Install from Downloads moves dir to Installed
  5. Update replaces installed and archives old version
  6. Compatibility check fails when scenario requires schema_version_min > current
  7. Compatibility check warns when cws_version_min > current (Q9a=b)
- Frontend vitest (≥4):
  1. Tab navigation switches view
  2. Export button triggers download
  3. Update flow shows compat confirm modal
  4. Compat warn modal proceeds on confirm

### ADRs
- `docs/adr/ADR-018-scenario-distribution.md` — local-only scope (no marketplace), export format, repository tabs strategy, update detection logic, backup-on-update path
- `docs/adr/ADR-019-scenario-dependency-management.md` — versioning rules (lenient semver), engine compat declaration, dependency types (preset only for v0.9), compat check timing + warn-or-reject policy

## Acceptance criteria (locked after Q sign-off)

To be populated post Q1-Q9 sign-off. Skeleton:

1. POST `/scenario/export` returns valid .zip
2. GET `/scenario/repository` returns 3-tab DTO
3. Import .zip with newer version → appears in Downloaded tab + Updates tab if installed counterpart exists
4. Update flow archives old version + activates new
5. Compatibility check rejects mismatched schema_version_min
6. Compatibility check warns + confirms on cws_version_min mismatch
7. Backend pytest 164 → ≥ 171 (+7). Frontend vitest 572 → ≥ 576 (+4).
8. ADR-018 + ADR-019 land.

## Commit grouping (5-6 commits)
1. backend repository + export + compat services + 4 endpoints
2. scenario_loader engine/dependencies fields + semver helpers + template updates
3. frontend repository tabs + ScenarioBrowserModal refactor + compat confirm modal
4. tests
5. ADRs

---

## What I'm waiting for from master

9 design Q's answered. After sign-off: fold + commit + dispatch codex.
