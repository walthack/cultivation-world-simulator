# v0.7 Spec — Creator Toolkit

Date: 2026-06-03
Author: Hassan
Status: **Ready for codex implementation** (御主 23:12 SGT 拍全部按推荐 Q1-Q8)
Branch: `feat/scenario-engine-v0.7` (branched off v0.6 HEAD `c35cbd60`)
Predecessor: v0.6 ready-to-PR (#5 → v0.5)

## Goal

Lower the barrier for players to AUTHOR their own scenario, not just import one. Three tools:
1. **Scenario Wizard** — UI flow to create a scenario from scratch
2. **Template Generator** — pre-built scenario starters (Historical / Fantasy / Sandbox)
3. **LLM Assisted Authoring** — describe your world in natural language, LLM generates scenario skeleton
4. **Schema Docs** — built-in reference docs so creators know what fields exist

After v0.7, a player can:
- Open "Create Scenario" wizard
- Optionally start from a template OR ask LLM to generate a skeleton
- Edit fields in the wizard form
- Export to a .zip (using v0.6 packaging) or save to local scenarios dir

## Scope (4 deliverables)

### 1. Scenario Wizard (frontend modal/page)
- Multi-step form: Basics (id/title/version/author/description/tags) → World preset selection → Initial state (avatars + relations) → Timeline events
- Live validation against the schema (reuse v0.6 validation logic)
- Save & continue between steps; can resume later (in-memory v0.7, persisted localStorage)

### 2. Template Generator (backend + frontend)
- Pre-built template JSON files bundled at `config/templates/scenario/<category>.json`
- Categories: Historical / Fantasy / Sandbox (3 starters)
- Each template is a minimal but valid scenario.json + timeline.json scaffold
- "Start from Template" button in the Wizard's first step

### 3. LLM Assisted Authoring (backend + frontend)
- New endpoint `POST /api/v1/command/scenario/generate` accepts `{description: str, hints: {locale, genre, ...}}`, calls existing `src/utils/llm/client.py::call_llm_json` with a schema-constrained prompt, returns a scenario.json draft
- Frontend: "Describe your world..." textbox → "Generate" button → fills the wizard form with LLM output (user can edit before saving)

### 4. Schema Docs (frontend)
- Built-in reference component showing the scenario.json schema fields with descriptions and examples
- Linkable from any wizard step ("?" icon next to each field)
- Initial content cribs from `docs/specs/scenario-metadata-schema.md` (v0.5) + `docs/specs/六朝-CWS-scenario-schema-v0.2.md`

## Out of scope (explicit deferral)

- ❌ Online templates / community-contributed templates (v0.9)
- ❌ Mid-scenario editing of a running game (v0.8 runtime control)
- ❌ Mod platform / plugin authoring (v1.0)
- ❌ Asset bundling (cover_image upload UI; v1.0 mod platform)
- ❌ Visual timeline editor (e.g. drag-drop event ordering) — text-based form only for v0.7

## Decision Matrix (御主 2026-06-03 23:12 SGT 拍全部按推荐)

| Q | 决策 |
|---|---|
| Q1 | (a) Step-by-step 6 步 wizard |
| Q2 | (a) 3 类 Historical / Fantasy / Sandbox |
| Q3a | 独立 `config/templates/scenario/*.json`，引用 bundled preset 不带新 preset |
| Q4a | (b) 复用 LLMMode.NORMAL（dedicated mode 留 v0.7+）|
| Q5 | (c) LLM 输出 schema 失败 → 自动重试 1 次 → 仍失败 surface raw 给用户 |
| Q6 | (c) Save & Activate 写盘 + Export .zip 下载，两个都做 |
| Q7 | (a) Schema Docs 弹 modal 从 "?" 按钮触发 |
| Q8 | (b) Draft localStorage per-session 持久化 |

---

## Original 8 Design Q's (for context — decisions above)

### Q1. Wizard form architecture
- (a) **Step-by-step wizard** with Next/Back buttons (Basics → World → Avatars → Relations → Timeline → Review)
- (b) **Single big form** with collapsible sections
- (c) **Tabbed form** with tabs at top

Recommend **(a) Step-by-step** — clearer for new authors, harder to skip required fields.

### Q2. Template categories
- (a) 3 categories per master roadmap: Historical / Fantasy / Sandbox
- (b) Expanded: + Wuxia(武侠) + Mystery + Slice-of-life + ...
- (c) Just 1 minimal "Blank" template; LLM does the rest

Recommend **(a) 3** — matches roadmap, keeps content authoring scope tight.

### Q3. Template content per category
What's IN each template?
- Historical: 3-4 avatars with 历史 dynasty refs (uses existing liuchao/sanguo style); 6-10 main events; uses bundled liuchao or sanguo presets
- Fantasy: 3-4 avatars with custom fantasy names; 6-10 events; uses bundled `default` preset (cultivation) OR define a minimal new "fantasy" preset?
- Sandbox: 2 avatars only; 1-2 events; minimal scaffold

Q3a: Do templates ship as separate files, OR are they DUPLICATES of existing scenarios (e.g. Historical template = a copy of sanguo's scenario.json)? Either way, do they reference EXISTING bundled presets, or include their own preset?

Recommend **separate JSON files at `config/templates/scenario/`, all reference bundled liuchao/default presets**. No new preset bundled with templates.

### Q4. LLM Authoring — model + cost
- v0.7 uses the existing `src/utils/llm/client.py` infrastructure with `LLMMode.NORMAL`
- User must have configured an LLM (via existing LLMConfigPanel.vue settings)
- If no LLM configured → "Generate" button disabled with helpful message pointing at settings

Q4a: Should we use a dedicated LLMMode for scenario authoring (e.g. `LLMMode.AUTHORING`) so users can configure a separate model for this task? Or reuse NORMAL?
  - (a) Dedicated `LLMMode.AUTHORING` — allows separate config for creative vs gameplay
  - (b) Reuse `LLMMode.NORMAL`

Recommend **(b)** for v0.7 simplicity. Can split later.

### Q5. LLM Authoring — output handling
- LLM returns JSON via `call_llm_json` with a schema constraint prompt
- Backend validates LLM output against scenario.json schema (reuse v0.6 deep validation)
- If LLM output FAILS validation:
  - (a) Surface raw output + validation errors; let user manually fix
  - (b) Auto-retry once with the validation errors fed back to LLM
  - (c) Both: auto-retry once, then surface raw if still failing

Recommend **(c)** — best UX with cost cap (max 2 LLM calls).

### Q6. Wizard output / save
- (a) Save to `$CWS_DATA_DIR/scenarios/<id>/` directly (like v0.6 install path)
- (b) Export as .zip (user downloads + can share); then v0.6 import flow
- (c) Both: "Save & Activate" (writes to disk) AND "Export .zip" (download)

Recommend **(c)** — flexible for share + immediate use.

### Q7. Schema Docs surface
- (a) Modal popup from "?" buttons in wizard
- (b) Side panel that opens alongside the wizard
- (c) Separate "Schema Reference" page route

Recommend **(a) Modal popup**. Side panel competes for screen space; separate route disrupts flow.

### Q8. Wizard persistence
- (a) In-memory only (close wizard = lose draft)
- (b) `localStorage` per-session draft
- (c) Backend-persisted drafts (`POST /scenario/draft`)

Recommend **(b)** — Simple, no backend churn, recovers from accidental close.

## Implementation contract (PENDING Q sign-off)

### Backend
- `src/server/services/scenario_templates.py` — loads `config/templates/scenario/<category>.json` files into a list
- `src/server/services/scenario_generate.py` — wraps `call_llm_json` with a system prompt that constrains output to scenario.json schema; handles validate-retry per Q5
- `src/server/api/public_v1/query.py` — add `GET /api/v1/query/scenario/templates` (list categories)
- `src/server/api/public_v1/command.py` — add `POST /api/v1/command/scenario/generate` (LLM authoring) + `POST /api/v1/command/scenario/save-draft` (Save & Activate)
- `config/templates/scenario/historical.json` + `fantasy.json` + `sandbox.json` (new content files)

### Frontend
- `web/src/components/game/panels/system/ScenarioWizardModal.vue` (NEW) — step-by-step form
- `web/src/composables/useScenarioWizard.ts` (NEW)
- `web/src/components/game/panels/system/ScenarioSchemaDocsModal.vue` (NEW) — schema reference
- `web/src/stores/scenarioWizard.ts` (NEW) — wizard draft state + localStorage sync
- `web/src/api/modules/scenario.ts` — extend with template list / generate / save-draft
- Wizard entry: "Create Scenario" button in `ScenarioBrowserModal.vue` (next to "Import…")

### Tests
- Backend (≥6 in `tests/test_scenario_authoring.py`):
  1. Template list endpoint returns 3 categories
  2. Each template loads as a valid scenario draft
  3. Generate endpoint with valid description returns scenario draft
  4. Generate endpoint with LLM mock returning invalid JSON → retry once
  5. Generate endpoint with persistent invalid output → returns raw + validation errors
  6. Save-draft endpoint persists to `$CWS_DATA_DIR/scenarios/`
- Frontend vitest (≥4):
  1. Wizard renders all 6 steps
  2. Validation prevents Next when required field empty
  3. Template selection populates wizard fields
  4. localStorage round-trip for draft

### ADRs
- `docs/adr/ADR-014-scenario-authoring-templates.md` — template format, category strategy, schema doc surface, wizard architecture
- `docs/adr/ADR-015-llm-assisted-scenario-authoring.md` — LLM prompt strategy, schema-constrained generation, validate-retry policy, fallback UX, cost control

## Acceptance criteria (locked after Q sign-off)

To be populated post Q1-Q8 sign-off. Skeleton:

1. ScenarioBrowserModal has "Create Scenario" button alongside "Import…"
2. Wizard opens, walks through 6 steps; each step validates required fields
3. "Start from Template" populates wizard from one of 3 templates
4. "Describe your world…" + Generate calls LLM, fills wizard
5. "Save & Activate" writes to `$CWS_DATA_DIR/scenarios/<id>/`, scenario shows in registry
6. "Export .zip" downloads a valid v0.6-importable zip
7. Schema docs modal opens from any wizard step
8. Wizard draft persists across page reload (localStorage)
9. Backend pytest 149 → ≥ 155 (+6). Frontend vitest 564 → ≥ 568 (+4).
10. ADR-014 and ADR-015 land.

## Commit grouping

5 commits on `feat/scenario-engine-v0.7`:
1. backend templates + generate + save-draft + 3 template JSON files
2. frontend ScenarioWizardModal + composable + store
3. frontend SchemaDocsModal + entry button + ScenarioBrowserModal extension
4. tests
5. ADR-014 + ADR-015

---

## What I'm waiting for from master

8 design Q's answered. After sign-off: fold-in + commit + dispatch codex.
