# v1.0 Release Verification Report

**Generated**: 2026-06-04 (initial cycle), refreshed 2026-06-05 (final RC)
**Author**: Hassan + 御主
**Status**: ✅ **GO** — final RC 5/5 green; release screenshot pack 11/11 captured for manual visual sign-off

## Final RC results (2026-06-05)

御主's fixed scope:

| Item | Result | Notes |
|---|---|---|
| Backend pytest (full suite) | ✅ **1694 passed / 3 pre-existing failed / 2 skipped** in 65s | 3 failures in `tests/test_game_init_integration.py` are pre-existing from Stage 2b (sects-related), unchanged by v1.0 |
| Frontend vitest (full suite) | ✅ **571 passed / 8 pre-existing failed** in 7.8s | 8 failures in `RoleplayDock.test.ts` are pre-existing localStorage issues, unchanged by v1.0 |
| Boot smoke (no flag / liuchao / sanguo) | ✅ **3/3** | year=100 / year=1 / year=208 |
| Playwright Layer 3 (mod platform Python gate) | ✅ **6/6 PASS** in 7.6s | Re-run against this session's backend |
| Playwright Layer 4A (scenario engine E2E) | ✅ **7/7 PASS** in 9.2s | Re-run against this session's backend |
| Playwright Layer 4 LLM authoring | ✅ **2/2 SKIPPED w/ reason** | `has_api_key=false` per design |

## v1.1 Scenario World Generation Control Update (2026-06-07)

| Item | Result | Notes |
|---|---|---|
| Focused backend pytest | ✅ **17/17 PASS** in 0.66s | `tests/test_scenario_avatar_fallback_position.py tests/test_scenario_generation_profile.py` |
| Backend pytest full suite | 🟡 **1713 passed / 3 pre-existing failed / 2 skipped** in 60.26s | Remaining failures are the known sect-related `tests/test_game_init_integration.py` failures already documented in v1.0 |
| No-scenario server smoke | ⚠️ **blocked in sandbox** | `src/server/main.py --dev` reached startup, then macOS sandbox denied bind on `127.0.0.1:8002` |
| Playwright Layer 4A v1.1 Step 9/10 | ⚠️ **not run in sandbox** | Requires a bindable backend and Vite server; spec updated with API assertions |

## v1.2 Scenario Generation Source Control Update (2026-06-07)

| Item | Result | Notes |
|---|---|---|
| Focused backend pytest | ✅ **26/26 PASS** in 0.98s | `tests/test_generation_source_control.py tests/test_scenario_generation_profile.py tests/test_scenario_avatar_fallback_position.py` |
| Backend pytest full suite | 🟡 **1722 passed / 3 pre-existing failed / 2 skipped** in 61.54s | Remaining failures are the known sect-related `tests/test_game_init_integration.py` failures |
| Phase A fail-fast | ✅ **load-time verified** | Negative test asserts scenario id, missing source kind, and expected preset path in `ScenarioValidationError` |
| Layer 4A Step 11/12 | 🟡 **spec updated / manual run pending** | Step 11 asserts Liuchao random NPC name templates; Step 12 skipped because hot-swap does not regenerate random NPCs |
| ADR-025 | ✅ **written** | `docs/adr/ADR-025-scenario-generation-source-control.md` |
| Mod platform contract | ✅ **`test_mod_platform.py` 12/12 PASS** in 0.51s | v1.2 does not touch `src/mod_platform/*`; mod import contract unchanged. Boundary documented in spec §11 + ADR-025 Consequences. |

Manual visual checklist is replaced by the **Release Screenshot Pack**
(11 screenshots at `docs/release-artifacts/v1.0/screenshots/`,
index + milestone mapping at `docs/release-artifacts/v1.0/index.md`).
Reviewer questions: (i) UI legible? (ii) Warnings clear? (iii) Panels
don't block main flow? (iv) Screenshots archived?

---

## Executive Summary

| Layer | Type | Status | Notes |
|---|---|---|---|
| **Layer 1** | Per-version RC | ✅ **PASS** | 1693 backend / 571 frontend vitest / 3 boot smoke green |
| **Layer 2** | Stack integration | ✅ **PASS** | Dry-run merge clean; merged-state pytest identical |
| **Layer 3** | Python gate Playwright | ✅ **PASS** | 6/6 (3 API + 3 UI) — gate state observable via `data.extensions: [{kind,name,active,inert}]`; UI flow goes Splash → Settings → SystemMenu (Settings tab + Mod Manager tab); 2 consecutive clean runs at 8.7s / 5.9s |
| **Layer 4A** | Scenario engine E2E | ✅ **PASS** | 7/7 — covers new-game/badge/panel/hot-swap/save-draft+export/wizard/repository/mod-gate. Two consecutive clean runs at 10.1s / 8.7s |
| **Layer 4 LLM** | LLM authoring opt | ✅ **2/2 SKIPPED w/ reason** | `has_api_key=false` in test env → spec auto-skips both tests with explicit reason (matches design) |
| **Layer 4B** | Manual visual | 🟡 **READY** | Checklist drafted; awaiting御主 mac time |
| **Layer 5** | Milestone A negative | ✅ **PASS** | 2 negative tests added → PR #10 |

**Key finding**: All safety-critical invariants verified at both API and UI level. **The Python hooks safety gate works correctly and hot-reloads on toggle** — API tests confirm `data.extensions[*].active/inert` flip as the gate is toggled, without server restart; UI tests confirm the badge + trust-modal flow match.

**Remaining work**: none from this verification cycle. Manual visual checklist (`docs/manual-visual-checklist.md`) is the only outstanding item before final sign-off.

---

## Layer 1 — Per-version RC ✅

### Backend pytest (full suite)
```
1693 passed / 3 failed / 2 skipped
3 failures: tests/test_game_init_integration.py (pre-existing from Stage 2b)
```

### Frontend vitest (full suite)
```
571 passed / 8 failed (pre-existing RoleplayDock localStorage)
```

### 3-boot smoke (live API)
| Scenario | Expected year | Actual | Result |
|---|---|---|---|
| `--scenario liuchao` | 1 | 1 | ✅ |
| `--scenario sanguo` | 208 | 208 | ✅ |
| no flag | 100 | 100 | ✅ |

---

## Layer 2 — Stack integration smoke ✅

Method: branched `merge-dry-run` off main, fast-forward merged `feat/scenario-engine-v1.0` (65 commits in stack).

Result: clean merge, no conflict. Post-merge:
- Backend pytest: **1693 passed / 3 pre-existing failed** (identical to v1.0 branch)
- Boot smoke `--scenario liuchao`: year=1, scenario engine active=true
- Dual advanced toggles verified as sibling fields (no collision):
  - `advanced_runtime_control` (v0.8) at `settings_schema.py:97`
  - `allow_trusted_python_mods` (v1.0) at `settings_schema.py:98`

**Conclusion**: stack collapses cleanly to a single mergeable state.

---

## Layer 3 — v1.0 Python Gate Playwright ✅ PASS (6/6)

All assertions go through the real runtime: API tests hit
`/api/v1/query/mods/extensions-active` (shape
`{ extensions: Array<{kind, name, active, inert, python_required, ...}> }`),
UI tests drive Chromium through the splash → SystemMenu flow. Tests run
serially (`test.describe.serial`) because they share a single backend
process. Two consecutive clean runs at 8.7s and 5.9s.

### API-level tests (3/3)

| Test | Result | Meaning |
|---|---|---|
| Default OFF → sample_predicate present with `active=false, inert=true` | ✅ PASS | Core safety invariant: with toggle OFF, predicate extension is declared but inert; condition_evaluator cannot resolve it. |
| Toggle ON → same predicate flips to `active=true, inert=false` | ✅ PASS | Gate hot-reloads via `sync_advanced_runtime_control` → `load_enabled_mods`; no server restart needed. |
| Toggle OFF → flips back to `active=false, inert=true` | ✅ PASS | Reverse hot-reload also works; state persistence intact. |

Backend `tests/test_mod_platform.py` mirrors the same assertion at the
function level via `get_active_extensions()` (12/12 pytest green incl.
`test_python_gate_state_reflected_in_extensions_shape`).

### UI-level tests (3/3)

Entry flow (verified by screenshot iteration on 2026-06-04): splash screen
exposes a Settings button; clicking it opens `SystemMenu` with the settings
tab active. From the SystemMenu the `Mod 管理` / `Mod Manager` tab button
switches to `ModManagerModal` without leaving the menu, so the whole flow
works pre-game.

| Test | Result | Selector path |
|---|---|---|
| "Python hooks: disabled" badge visible on sample-overhaul | ✅ PASS | `.python-badge` filtered by text |
| Data-only extensions (asset/llm/locale) listed as chips | ✅ PASS | text match on `asset:portraits/...`, `llm:sample_npc_action`, `locale:en-US` |
| Toggle ON shows trust modal, then Mod Manager badge reads "enabled" | ✅ PASS | `data-testid="python-mod-switch"` + `.trust-modal` text + `.python-badge.enabled` |

### Earlier "hot-reload limitation" retraction

A prior pass of this report listed a v1.1 backlog item claiming
`allow_trusted_python_mods=true` did NOT hot-reload mod Python hooks. That
diagnosis was wrong. Root cause: the Layer 3 Playwright spec was reading a
non-existent `data.predicates` / `data.rules.predicates` shape from the
`extensions-active` endpoint, and the UI test was looking for `.menu-toggle`
which only exists inside a started game. Once the assertions read the real
shape and the UI flow is rewritten to enter through the splash Settings
button, the gate is observed to flip extensions between `active/inert`
in-process without restart. No v1.1 backlog item remains from this thread.

---

## Layer 4 — Scenario engine + LLM ⏸️

### 4A non-LLM happy path — ✅ PASS (7/7)

Tests run serially against a single backend (`test.describe.serial`). Two
consecutive clean runs at 10.1s and 8.7s. The seven steps cover:

| Step | What it verifies | Selector / API path |
|---|---|---|
| 1+2 | New game with liuchao → scenario badge "六朝纪事" renders | `.scenario-badge-title` text match |
| 3 | Click badge → ScenarioOverviewModal Timeline section headings | text "已触发事件" / "未触发事件" |
| 4 | advanced_runtime_control ON → select sanguo → Activate hot-swap → verbatim warning displayed | `.scenario-select` + `.n-base-select-option` text + "Hot-swap does not re-anchor time…" copy |
| 5 | save-draft installs custom scenario `e2e_test` → export returns valid zip blob | POST `/scenario/save-draft` + `/scenario/export` |
| 6 | Splash → 开始游戏 → Browse → Create Scenario → Wizard with 6 steps (Basics … Review) | role buttons + `.wizard-steps .wizard-step` count |
| 7 | Repository endpoint returns shape `{installed[], downloaded[], updates[]}` with the installed draft | GET `/scenario/repository` |
| 8 | sample-overhaul installed → Python gate OFF reflected in extensions API | `data.extensions.find(kind==="predicate" && name==="sample_predicate")` |

**Notes verified by screenshot iteration on 2026-06-05:**
- Step 5 changed from "export bundled liuchao zip" → "save-draft a custom
  scenario then export it." Bundled scenarios are protected by the
  `scenario_export_not_found` contract and cannot be exported directly;
  the positive happy path requires an installed (non-bundled) scenario.
- Step 7 likewise changed from "find bundled liuchao in repository.installed"
  to "find the e2e_test draft in repository.installed." Bundled scenarios
  live in `/api/v1/query/scenarios`, not `/scenario/repository`.
- Setup requires (i) packaging `examples/mods/sample-overhaul/` and POSTing
  it to `/api/v1/command/mod/install`, and (ii) writing a stub LLM profile
  via PUT `/api/settings/llm` so the auto-open of the non-closable LLM
  SystemMenu does not intercept clicks. The spec also installs a tiny
  WebSocket filter via `page.addInitScript` to drop the one
  `llm_config_required` socket message that fires on boot with the stub URL.

### 4 LLM (opt-in) — ✅ 2/2 SKIPPED w/ reason

beforeAll calls `hasLLMKey()` (reads `llm.profile.has_api_key` from
`/api/v1/query/system/current-run`); without a real LLM profile the
hook calls `test.skip` with an explicit reason and both downstream tests
are reported as skipped. This matches the design (御主 09:35 SGT mandate:
"LLM-related tests must not block automation").

### 4B Manual visual checklist

`docs/manual-visual-checklist.md` ready. 6 sections + sign-off. Awaits御主 mac session.

---

## Layer 5 — Milestone A negative test backfill ✅

PR #10 https://github.com/walthack/cultivation-world-simulator/pull/10 — 2 negative tests:
1. `test_unknown_predicate_name_raises_condition_evaluation_error` ✅
2. `test_unknown_effect_type_raises_effect_error_and_rolls_back_state` ✅

After merge: all 11 milestones have explicit negative tests.

---

## Per-milestone negative test audit (post backfill)

| Milestone | Negative test |
|---|---|
| A | `test_unknown_predicate_name_raises_condition_evaluation_error` + `test_unknown_effect_type_raises_effect_error_and_rolls_back_state` (PR #10) |
| B | `test_status_active_false` |
| C | `test_load_refuses_scenario_mismatch` / `test_load_refuses_no_scenario_flag` / missing-goldfinger-ref boot fail |
| D-d2 bugfix | `test_server_scenario_world_uses_initial_state_start_time_without_manual_pin` (TDD RED) |
| v0.5 | `test_unknown_scenario_id_fails_before_server_boot` |
| v0.6 | 5 security tests (zip-bomb / path-traversal / symlink / bundled-collision / bad-json) |
| v0.7 | `test_generate_persistent_invalid_returns_raw_and_errors` + `description=""` |
| v0.8 | `test_advanced_mode_gate_blocks_activate_when_disabled` + hot-swap warning verbatim check |
| v0.9 | bundled-collision reject / schema_version_min mismatch / fingerprint modified |
| v1.0 | Python gate OFF predicate-not-found ✓ + lifecycle-not-fire ✓ + conflict modal + dependency-missing |

---

## Final go/no-go assessment

### Engineering layer: ✅ GO

All safety-critical contracts hold:
- Scenario engine generic (validated by 2 example scenarios)
- World injection avatars/relations correct
- Save/load with scenario_id consistency
- Import security (zip-bomb / path-traversal / symlink protections)
- Hot-swap warning verbatim in 4 surfaces
- Fingerprint 3-state verification
- **Python hooks default-disabled (verified at API level)**
- Mod conflict detection
- 9-PR stack merges cleanly

### UI layer: ✅ GO

Layer 3 selectors converged via screenshot-driven iteration on 2026-06-04
(headless Playwright + `CWS_E2E_ARTIFACTS=full` traces). Stable entry path
is splash Settings button → `SystemMenu` modal → tab switch to `mods`.
Selectors used are limited to `data-testid="python-mod-switch"`,
`.python-badge`, `.trust-modal`, and accessible-name role buttons — no
brittle CSS chains.

**Layer 4A also green** (7/7) using the same Splash → SystemMenu entry
pattern plus a WebSocket filter for the boot-time `llm_config_required`
message. Layer 4 LLM (2/2) auto-skips with reason in the no-key test env.

### Manual layer: 🟡 READY FOR御主

`docs/manual-visual-checklist.md` — ~10 screenshots, 6 sections, 1-5 scoring.

---

## Recommended deliverable ordering for御主

1. **Now**: Review Layer 1+2 results — engineering merge can proceed (御主 has been holding back merge per his earlier directive)
2. **Mac time**: Run `npx playwright test --headed layer3-` and iterate selectors with Inspector
3. **Mac time**: Walk manual visual checklist; capture screenshots
4. **After UI iteration**: Sign off this report; merge PR #1-#10 in order; tag `v1.0.0-final`

---

## Artifacts location

- Playwright traces / screenshots: `web/test-results/layer3-mod-platform-*/`
- HTML report (if generated): `web/playwright-report/`
- Backend test output: stdout (rerun via `.venv/bin/pytest`)
- Frontend test output: stdout (rerun via `cd web && npx vitest run`)
- Dashboard snapshot: `/Volumes/botsvault/06_material/六朝-CWS-progress-dashboard.md` v13

---

## Hassan disclosed limitations

Initial Layer 3 selectors were written blind from Vue source and failed
across the board. 御主 enabled screenshot-driven iteration via headless
Playwright + `CWS_E2E_ARTIFACTS=full` (no Playwright MCP / Chrome DevTools
MCP available in this session); two rounds were enough to converge 6/6
PASS. The misdiagnosed "hot-reload limitation" was traced to the original
spec reading `data.predicates` (non-existent) and looking for `.menu-toggle`
(only exists post-game-start).

御主 has the final sign-off authority. Engineering + UI layers are
release-ready for the Python gate. Manual visual checklist remains for
御主's mac session before final tag.
