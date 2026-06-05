# v1.0 Spec — Generic Mod Platform

Date: 2026-06-04
Author: Hassan
Status: **Ready for codex implementation** (御主 2026-06-04 01:20 SGT 拍 Q1-Q12 + Q1 加 Python hooks 默认禁用 safety gate)
Branch: `feat/scenario-engine-v1.0` (branched off v0.9 HEAD `701f6b7e`)
Predecessor: v0.9 ready-to-PR (#8 → v0.8)
Final version of the roadmap — closes the Scenario Engine → Mod Platform upgrade.

## Goal

Promote the existing Scenario Engine to a **Generic Mod Platform**. Beyond just scenarios, players can install/enable mods that add or override:
- **Rules**: custom predicate evaluators + custom effect appliers (DSL extension)
- **Assets**: portraits / icons / localization strings (asset injection)
- **LLM prompts**: NPC behavior / world events / story generation (prompt override)
- **Code**: Python plugin hooks at well-defined extension points

After v1.0:
- Players install mods like `xianxia-overhaul.mod` or `wuxia-story-pack.mod`
- Creators ship Mods alongside scenarios (or stand-alone)
- A "Total Conversion" mod can replace bundled liuchao/sanguo entirely with original content

## Critical scope decision (driving every Q below)

**Plugin trust model = "trust + clear warning"**, NOT sandbox.

CWS is a single-player desktop app. Sandboxing Python plugins (RestrictedPython, separate process, etc.) is heavy engineering for marginal safety — users running an untrusted .mod from random sources can compromise the host regardless of any sandbox we build. Industry practice for desktop modding (Skyrim, Factorio, BG3) is "you install it, you trust it" + transparent loading.

v1.0 v0 design:
- Mods are explicitly loaded code; no auto-execution from untrusted sources
- Each mod load shows the user a confirmation modal listing what it touches (rules / assets / LLM prompts / Python hooks)
- Mod ships with a fingerprint (v0.9 extension) so the user can verify integrity
- We do NOT add a Python sandbox in v1.0 — documented as "out of scope, may be added later if community needs"

## Decision Matrix (御主 2026-06-04 01:20 SGT)

| Q | 决策 |
|---|---|
| Q1 | (a) trust + warn modal **+ 关键 constraint**：Python hooks 默认禁用 |
| Q2 | (c) .mod zip + folder 都支持 |
| Q3 | `$CWS_DATA_DIR/mods/<mod_id>/` |
| Q4a | (b) predicate 冲突用 conflict modal |
| Q5a | (b) localization 冲突用 conflict modal |
| Q6a | (b) LLM prompt 模板用 plain f-string |
| Q7 | (b) Python hooks 支持 rules + lifecycle |
| Q8a | (a) dependency schema 扩 type="mod" |
| Q9 | 无 mod 时现有 scenario + pytest 必须不破 |
| Q10 | (a) 系统菜单单独加 Mod Manager tab |
| Q11a | mod 复用 sha256 fingerprint |
| Q12 | (a) marketplace 不进 v1.0，继续 strictly local |

---

## CRITICAL: Q1 Python Hooks Safety Gate（御主 verbatim constraint）

御主 原话：
> "Python hooks can be installed, but not executed unless the user explicitly enables 'Allow trusted Python mods' in Advanced Settings."

### 默认状态（toggle OFF）
- ✅ 可安装 mod（任何类型）
- ✅ 可启用 data-only mod：assets / LLM prompts / localization / 任何**非 Python 代码**的扩展
- ❌ **不执行 Python hooks**：predicates / effects / lifecycle hooks 全部 inert（声明但不注册到 runtime）
- ✅ Mod Manager UI 显示 mod 信息 + extension list + "Python hooks: disabled" 状态指示

### Advanced toggle ON
- ⚠️ 启用前弹 trust warning modal："You are about to enable Python mod execution. Untrusted mods can do anything the game can do. Continue?"
- ✅ Confirm 后：Python predicates / effects / lifecycle hooks 全部 active
- ✅ Mod Manager UI 显示 "Python hooks: enabled" with warning badge

### 实装位置
- Settings 字段：`session.allow_trusted_python_mods: bool` (default False)
- ScenarioOverviewModal 的 advanced gate（v0.8）的兄弟 setting
- mod_loader：根据 setting 决定是否注册 Python 扩展
- 每次 game/start 时检查 setting；toggle 状态改变要求重启 session（生产中切换很 footgun）

### 原因（御主 原话）
> "trust + warn 可以接受，但不能做到'安装即执行'。单机 mod 可以信任用户判断，但要给用户明确的安全闸门。"

### Data-only vs Python mod extensions 分类（Hassan 整理）

| 扩展类型 | Python required? | Default state | Advanced toggle needed? |
|---|---|---|---|
| Asset overlay (portraits/icons) | No (files only) | Active | No |
| LLM prompt overlay (text templates) | No (plain text) | Active | No |
| Localization overlay (text strings) | No (text only) | Active | No |
| Custom predicates (.py implementations) | Yes | Inert | Yes |
| Custom effects (.py implementations) | Yes | Inert | Yes |
| Lifecycle hooks (.py callables) | Yes | Inert | Yes |
| Mod dependencies declarations | No (metadata only) | Validated regardless | No |

Mod 可以同时声明 data-only + Python；只有 Python 部分受 toggle gate。Data-only 部分一直 active。

---

## v1.0 范围锁定（御主 verbatim）

**In scope (v1.0)**：
- local generic mod platform
- plugin hooks (Q7 lifecycle + DSL extensions)
- rule extensions (predicates + effects via Python)
- asset overlay
- LLM prompt overlay
- mod dependencies
- mod manager
- sample mod (`examples/mods/sample-overhaul/`)

**Explicitly excluded (v1.0)**：
- marketplace
- online hosting
- remote update
- Python sandbox
- multi-user moderation
- paid mods

---

## Original 12 Design Q's (for context — decisions above)

### Q1. Plugin trust model
- (a) **Trust model with transparent loading** (recommended): no sandbox, but each install shows modal listing extension points the mod touches; user confirms
- (b) Lite sandbox via RestrictedPython (limits subset of Python; some mods break)
- (c) Heavyweight process-isolation sandbox (full safety; complex; performance cost)

Recommend **(a)** for v1.0. Industry-standard for desktop modding. (b)/(c) deferable.

### Q2. Mod package format
- (a) `.mod` extension = .zip with internal structure mirroring v0.6's scenario .zip but with extra dirs (`rules/`, `assets/`, `llm/`, `code/`)
- (b) Folder drop only
- (c) `.mod` zip + folder drop both

Recommend **(c)** — zip for sharing, folder for in-development modders. Aligns with v0.6 import flow.

### Q3. Mod install location
- `$CWS_DATA_DIR/mods/<mod_id>/` — bundled cws-fork stays untouched (mods cannot replace bundled files in-place; they OVERLAY via load order)
- Each mod has `mod.json` metadata at top level

### Q4. Rule Extensions
v1.0 supports custom predicates + custom effects via Python code in mods:
- `mod.json` declares `extensions.rules.predicates: ["my_predicate"]` + `extensions.rules.effects: ["my_effect"]`
- Mod ships `rules/predicates.py` exporting functions named per the declared list, signature `def my_predicate(state, args) -> bool`
- Same for effects: `def my_effect(state, args) -> None`
- On load: cws scans declared names + monkeypatches into `condition_evaluator` + `effect_applier` registries

Q4a: collision policy — two mods both declare predicate `my_predicate`?
- (a) Load order wins (later mod overrides)
- (b) Conflict modal asks user
- (c) Reject second mod
- Recommend **(b)** — explicit conflict handling.

### Q5. Asset Extensions
Mods can ship portraits / icons / localization:
- `mod.json` declares `extensions.assets.portraits: [...]` etc.
- Asset files in `assets/` subdir
- On install, cws stages assets in a mod-overlay area; when game requests `<asset_path>`, mod-overlay paths checked first, then bundled fallback.

Q5a: localization conflict — mod A and mod B both override `string.greeting.morning`?
- Same as Q4a — recommend **(b)** conflict modal.

### Q6. LLM Extensions
Mods can override prompt templates: NPC behavior / world event / story generation / character introspection.
- `mod.json` declares `extensions.llm.prompts: [{key: "npc_action", template_path: "llm/npc_action.jinja"}]`
- The existing `src/utils/llm/client.py::call_llm_with_template` already has a template-key indirection; v1.0 extends template resolution to check mod overlays first.

Q6a: prompt template syntax — what templating engine?
- (a) Jinja2 (powerful, slightly larger dep)
- (b) Plain f-string-like format placeholders (lightweight)
- (c) Mustache (logic-less)
- Recommend **(b)** for v1.0 — minimal dep, mods that need Jinja-class logic can use Python hooks. Matches existing template plumbing.

### Q7. Python hooks (Code Extensions)
At what extension points can mods hook?
- (a) Minimal: just rules predicates/effects (already in Q4)
- (b) Minimal + lifecycle hooks: `on_world_init(world)`, `on_step(world, ctx)`, `on_avatar_death(avatar)`, `on_scenario_event_dispatched(event)`
- (c) Expansive: every internal function exposed as hook

Recommend **(b)** for v1.0. (a) too limited (no real "mod" feel), (c) bloats the API surface and locks us in.

### Q8. Mod combination & load order
When multiple mods are enabled:
- Load order = user-controlled list in `$CWS_DATA_DIR/mods_load_order.json`
- UI: drag-reorder list in Mod Manager
- Later mods can override earlier; conflict modal (Q4a/Q5a) when collisions
- Mods declare dependencies on other mods via `dependencies.[].type: "mod"` (extends v0.9's preset-only deps)

Q8a: extend v0.9's `dependencies` to include `"mod"` type?
- (a) Yes — natural extension
- (b) No, keep v0.9 simple (preset only); v1.0 introduces separate mod-deps field
- Recommend **(a)** — unify the dependency model.

### Q9. Backward compatibility
- Existing scenarios (liuchao/sanguo + creator-toolkit output) MUST keep working with NO mods enabled
- Existing pytest suite must stay green
- ScenarioBrowserModal still shows installed scenarios; new "Mods" sibling area added separately

### Q10. Mod Manager UI placement
- (a) Add "Mod Manager" tab to system menu (separate from Scenarios)
- (b) Add "Mods" tab inside ScenarioBrowserModal (treat mods as a new repository tab next to Installed/Downloaded/Updates)
- (c) Standalone modal

Recommend **(a)** — mods are conceptually adjacent to but distinct from scenarios. Separate UX surface.

### Q11. Mod metadata schema
`mod.json` top-level fields:
```json
{
  "mod_id": "wuxia-overhaul",
  "name": "Wuxia Overhaul",
  "version": "1.0.0",
  "author": "...",
  "description": "...",
  "fingerprint": "sha256:..." (v0.9 extension),
  "engine": { "schema_version_min": "0.2", "cws_version_min": "3.4.0" },
  "dependencies": [{ "type": "preset", "id": "default" }, { "type": "mod", "id": "base-pack", "version_req": ">=1.0" }],
  "extensions": {
    "rules": { "predicates": [...], "effects": [...] },
    "assets": { "portraits": [...], "icons": [...], "localizations": {...} },
    "llm": { "prompts": [...] },
    "code": { "hooks": ["on_world_init", "on_step", ...] }
  }
}
```

Q11a: Same fingerprint algorithm as v0.9 scenarios?
- Recommend **yes** — reuse `scenario_fingerprint.py` extended to compute hash over mod.json + all referenced files (rules .py / assets / llm templates / code hooks). Different content type, same algorithm.

### Q12. Marketplace (re-confirm deferral)
v1.0 was originally the place where marketplace might land (per v0.9 spec deferral note).

- (a) Still local-only: same v0.9 model (drop .mod file in Downloads folder)
- (b) Add HTTP-based mod fetcher (GitHub releases API + URL whitelist? Generic URL?)

Recommend **(a)** — keeps v1.0 scope manageable. Online marketplace == separate community/infra problem. Even Skyrim/Factorio modding works fine via web download + manual install.

## Implementation contract (PENDING Q sign-off)

### Backend
- `src/mod_platform/` (new module):
  - `mod_loader.py` — loads mods from `$CWS_DATA_DIR/mods/`, parses mod.json, registers extensions
  - `mod_registry.py` — tracks enabled/disabled mods + load order
  - `mod_extension_points.py` — defines stable extension point API (Python hook signatures)
  - `mod_import.py` — accepts .mod / folder, validates, installs
  - `mod_conflict.py` — detects collisions, surfaces to UI
- `src/scenario/condition_evaluator.py` + `effect_applier.py` — extend registries to accept mod-contributed predicates/effects (DSL extension)
- `src/utils/llm/client.py` — extend `call_llm_with_template` to check mod overlays before bundled templates
- `src/server/api/public_v1/command.py` — endpoints: mod/install / uninstall / set-enabled / reorder / export
- `src/server/api/public_v1/query.py` — endpoints: GET /mods/installed / GET /mods/load-order

### Frontend
- New `ModManagerModal.vue` + tabs (Installed mods / Downloaded mods / Load Order / Extensions inspection)
- Mod card shows: name / version / author / fingerprint / extensions list / enable/disable toggle / reorder handle
- Conflict modal when install detects collision
- System menu: "Mod Manager" entry

### Tests
- Backend (≥10 in `tests/test_mod_platform.py` + `tests/test_mod_extension_points.py`):
  - Mod install + load + extension registration
  - Predicate override picked up by dispatcher
  - Effect override applied
  - Asset overlay path resolves
  - LLM template overlay
  - Lifecycle hook fires on world_init / step
  - Load order respected when 2 mods declare same name (Q4a=b conflict resolution)
  - Dependency check fails when mod A requires mod B not installed
  - Disable mod removes its extensions
  - Mod fingerprint verification
- Frontend vitest (≥6):
  - ModManagerModal renders mod list
  - Enable/disable toggle works
  - Reorder load order via drag
  - Conflict modal on install
  - Extension inspection view
  - Fingerprint badge per mod

### ADRs
- `docs/adr/ADR-020-mod-platform-architecture.md` — trust model, extension point API, load order semantics, conflict policy
- `docs/adr/ADR-021-mod-asset-overlay.md` — asset overlay scheme, localization conflict handling
- `docs/adr/ADR-022-mod-llm-prompt-overrides.md` — prompt template overlay, plain f-string syntax, fallback to bundled
- `docs/adr/ADR-023-mod-python-hooks.md` — hook signatures, lifecycle event list, trust model rationale

## Out of scope (locked deferrals)

- ❌ Online marketplace (re-confirmed; v1.0 stays local)
- ❌ Python sandbox (Q1=a; "trust + warn" model only)
- ❌ Mod editing UI (creators author externally; v1.0 is install/manage only)
- ❌ Hot-reload of mods at runtime (mods load at game-start)
- ❌ Mod scripting API beyond declared extension points (no full embedded scripting language)

## Acceptance criteria (locked after Q sign-off)

To be populated post Q1-Q12 sign-off. Skeleton:

1. POST `/mod/install` accepts .mod zip, installs to `$CWS_DATA_DIR/mods/<id>/`
2. Mod with predicate "my_pred" registers it; scenario can use `my_pred` in trigger condition
3. Mod with effect "my_effect" registers it; scenario can use `my_effect`
4. Asset overlay: mod-supplied portrait at `portraits/xianxia_male.png` resolved before bundled
5. LLM prompt overlay: mod-supplied template for `npc_action` used by `call_llm_with_template`
6. Lifecycle hook: mod with `on_step` fires on every simulator step
7. Conflict modal triggered when 2 enabled mods declare same predicate name
8. Disable mod → its extensions removed from runtime registries
9. Backend pytest 174 → ≥ 184 (+10). Frontend vitest 576 → ≥ 582 (+6).
10. ADR-020 / ADR-021 / ADR-022 / ADR-023 land.
11. Full 1682 pre-v1.0 pytest still passes (no breakage to default game flow)
12. Sample mod ships at `examples/mods/sample-overhaul/` for documentation reference

## Commit grouping (6-7 commits on `feat/scenario-engine-v1.0`)
1. Mod loader + registry + extension points + import + conflict
2. Engine DSL registry extension (predicates / effects mod hooks)
3. Asset overlay + LLM prompt overlay
4. Python lifecycle hooks
5. Backend API endpoints
6. Frontend ModManagerModal + Mod cards + Settings entry
7. Tests + ADRs (4 ADRs + sample mod)

---

## What I'm waiting for from master

12 design Q's answered. After sign-off:
1. Fold Q decisions into spec, commit
2. Dispatch codex with focused brief
3. Hassan verify + 6-7 commits + PR #9 → v0.9 + tag `v1.0-mod-platform` + dashboard archive
4. v1.0 closes the autonomous-to-v1.0 directive — roadmap complete

This is the FINAL version. Take longest to design well.
