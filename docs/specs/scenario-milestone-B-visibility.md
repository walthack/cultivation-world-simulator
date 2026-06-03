# Milestone B Spec — Scenario Visibility

Date: 2026-06-03
Author: Hassan
Status: Ready for codex implementation
Master signoff: 2026-06-03 20:25 SGT (Milestone roadmap 13:07 SGT + execute-to-v0.4 directive 20:27 SGT)
Branch: `feat/scenario-engine-milestone-B` (branched off stage-2d HEAD `a925f803`)

## Goal

Make the active Scenario Engine visible to the player in the running UI. Today, `--scenario liuchao` boot ships scenario data into `world.scripted_scenario` but the player has zero UI surface to see the scenario is active, what's in it, or which timeline events have fired. Milestone B adds the **read-only visibility layer**: a scenario status API + 3 UI components (badge / panel / triggered events list).

No injection logic changes. No avatar / relation / save-load work (those are Milestone C). No save format changes.

## Scope (4 deliverables)

### 1. Scenario Status API (backend)
- Endpoint: `GET /api/v1/query/scenario/status`
- Registered in `src/server/api/public_v1/query.py` mirroring the existing query pattern
- Response payload (typed via Pydantic):
  ```json
  {
    "ok": true,
    "data": {
      "active": true,
      "scenario_id": "liuchao",
      "title": "六朝纪事",
      "version": "1.0",
      "world_background": "...",
      "preset_id": "liuchao",
      "controlled_avatar": "cheng-zongyang",
      "timeline": {
        "total_events": 9,
        "triggered_count": 2,
        "events": [
          { "id": "liuchao-opening", "name": "六朝开局", "type": "side_event", "trigger": {"year": 1, "month": 1}, "dynasty_id": null, "at_region_id": null, "triggered": true, "triggered_month_stamp": "1-1" },
          { "id": "wang-zhe-passes-jiuyang", "name": "王哲传程宗扬九阳", "type": "main", "trigger": {"year": 2, "month": 3}, "dynasty_id": "song", "at_region_id": "linan", "triggered": false }
        ]
      },
      "world_flags": { "liuchao_opening_seen": true }
    }
  }
  ```
- When `world.scripted_scenario is None`: respond `{"ok": true, "data": {"active": false}}`
- Read-only — no mutation endpoints

### 2. Scenario Badge (frontend)
- Small visual element showing "📜 六朝纪事" (icon + scenario title) when scenario is active
- Placement: top-right of the game header (next to dynasty / year display), or wherever existing CWS UI puts "global game state badges". Codex picks the spot that fits existing visual conventions.
- Click opens the Scenario Panel modal (deliverable 3)
- Hidden when no active scenario (graceful — default game UI unchanged)
- Component file: `web/src/components/game/panels/ScenarioBadge.vue` (or fitting subdir)

### 3. Scenario Panel (frontend modal)
- Modal showing scenario detail:
  - Title + version + world_background (formatted prose)
  - Preset ID (small, technical)
  - Timeline section (deliverable 4 goes inside this)
  - Controlled avatar indicator (small badge showing currently controlled NPC if any)
- Pattern after `DynastyOverviewModal.vue` for shape consistency
- Component file: `web/src/components/game/panels/ScenarioOverviewModal.vue`
- Composable: `web/src/composables/useScenarioOverviewModal.ts`
- Modal opens from Badge click + from system menu entry (one of those, codex picks based on existing pattern)

### 4. Triggered Events List (inside Panel)
- Chronological list of fired scenario events
- Each row: name + scenario event ID (small) + trigger year/month + triggered month_stamp ("已触发于 Y3M1") + dynasty/region hints (if present)
- Section heading: "已触发事件" / "未触发事件" (two sub-sections, fired ones bold first, upcoming ones grayed)
- No interaction — purely informational
- Lives inside `ScenarioOverviewModal.vue`

## Store + types

- Pinia store: `web/src/stores/scenario.ts` — caches the `/scenario/status` response, refetches on key game-state changes (post-step events, post-resume, post-game-start)
- DTO types in `web/src/types/api.ts` for the scenario status response
- API client: add a function to `web/src/api/modules/` (likely a new `scenario.ts` module mirroring `dynasty.ts` shape) that calls `/api/v1/query/scenario/status`

## Backend assemblers / services

- Likely a small `src/server/assemblers/scenario_status.py` mirror of `dynasty_overview.py` pattern
- Reads `runtime.world.scripted_scenario` + the `ACTIVE_SCENARIO` resolved scenario for things like title/version/world_background

## Tests required

### Backend (≥3 new tests in `tests/test_api_scenario_status.py`)
1. Active scenario → returns `active=true`, scenario_id matches, timeline.total_events > 0, triggered_count starts at 0
2. After simulator advances to year 1 month 1 and `liuchao-opening` fires → triggered_count == 1, that event has `triggered: true`
3. No scenario active → returns `active=false`

### Frontend (≥4 new vitest cases in `web/src/__tests__/components/game/scenario/`)
1. ScenarioBadge renders title when status.active === true
2. ScenarioBadge does NOT render when status.active === false
3. ScenarioOverviewModal renders timeline events grouped by triggered/untriggered
4. ScenarioOverviewModal opens from badge click

## Forbidden scope (Milestone C)

- No `avatar` injection into `world.avatar_manager`
- No `relation` injection
- No `ScriptedScenarioState` save/load persistence
- No mutation endpoints (read-only milestone)
- No engine semantic changes
- No `.venv/` touches

## Acceptance criteria

1. `GET /api/v1/query/scenario/status` with `--scenario liuchao` active returns the payload above
2. `GET /api/v1/query/scenario/status` with no `--scenario` returns `{"active": false}`
3. Boot with `--scenario sanguo` → API returns scenario_id "sanguo", title "三国乱世" (or whatever sanguo scenario.json says — sanguo scenario.json `title` field)
4. UI: badge shows in header when scenario active, hidden when default game
5. UI: clicking badge opens panel; panel shows timeline grouped fired/upcoming
6. UI: panel shows world_background text without HTML injection vulnerabilities (escape user content per existing CWS conventions)
7. Backend pytest: 122 → ≥ 125 (+3 scenario status API tests). No engine regressions.
8. Frontend vitest: existing tests still pass + ≥ 4 new tests for scenario components
9. Full pytest: 1629 baseline → 1629 + new (3 pre-existing failures unchanged)
10. **No regressions in default-game UI** (no scenario active → no badge, no panel, normal game flow unchanged)

## Files expected to touch

New:
- `src/server/api/public_v1/query.py` — add scenario route (or modify if existing query.py)
- `src/server/assemblers/scenario_status.py`
- `src/server/services/` — possibly add `scenario_status_service.py` if logic warrants
- `web/src/api/modules/scenario.ts`
- `web/src/types/api.ts` — add scenario DTOs
- `web/src/stores/scenario.ts`
- `web/src/components/game/panels/ScenarioBadge.vue`
- `web/src/components/game/panels/ScenarioOverviewModal.vue`
- `web/src/composables/useScenarioOverviewModal.ts`
- `tests/test_api_scenario_status.py`
- `web/src/__tests__/components/game/scenario/ScenarioBadge.test.ts`
- `web/src/__tests__/components/game/scenario/ScenarioOverviewModal.test.ts`
- `docs/adr/ADR-008-scenario-visibility-readonly-layer.md`

Modified (additive):
- `web/src/App.vue` — wire badge + modal mount
- `web/src/components/game/panels/index.ts` if there's a registry

## ADR-008 must cover
- Read-only visibility decision (why no mutation surface)
- Badge placement choice + rationale
- DTO shape choice (`active: boolean` wrapper vs nullable scenario_id at top)
- Refetch trigger choice (on every step? on event? on socket message?)
- Store strategy (Pinia, mirror existing patterns)

## Commit grouping

~3-4 commits on `feat/scenario-engine-milestone-B`:
1. `feat: Milestone B — scenario status API endpoint + assembler` (backend)
2. `feat: Milestone B — scenario store + api module + DTOs` (frontend plumbing)
3. `feat: Milestone B — ScenarioBadge + ScenarioOverviewModal + triggered events list` (UI)
4. `test: Milestone B — backend + frontend tests + ADR-008` (tests + doc)

If `.git/index.lock` blocks, write all + report unstaged.

## Reporting format
```
WROTE (new files):
  <list>
MODIFIED (existing files):
  <list>
NEW BACKEND TEST COUNT: 122 -> <N>
NEW FRONTEND VITEST COUNT: baseline -> <M>
COMMITS: <sha + subject> | unstaged | blocked
ADR PATH: docs/adr/ADR-008-...
UI DECISION NOTES: <badge placement / modal trigger / refetch strategy in one sentence each>
DEVIATIONS FROM SPEC: <list>
```
"PARTIAL — done: X, remaining: Y" if you bail.
