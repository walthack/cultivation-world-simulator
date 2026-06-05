# v1.0 Release Screenshot Pack

Generated 2026-06-05 by `web/e2e/release-screenshots.spec.ts` (headless
Chromium, viewport 1280×720, against a fresh `CWS_DATA_DIR` with a stub
LLM profile, the `sample-overhaul` mod pre-installed, and an `e2e_test`
scenario draft installed via `/api/v1/command/scenario/save-draft`).

Re-generate from the repo root with:

```bash
# Terminal 1 — fresh data dir, backend on 8002
rm -rf /tmp/cws-e2e-data && mkdir /tmp/cws-e2e-data
CWS_DATA_DIR=/tmp/cws-e2e-data CWS_NO_BROWSER=1 \
  .venv/bin/python src/server/main.py --dev

# Terminal 2 — vite on 5173
cd web && npm run dev

# Terminal 3 — pack the sample mod + install it + run the spec
(cd examples/mods/sample-overhaul && zip -r /tmp/sample-overhaul.mod .)
curl -X POST -F "file=@/tmp/sample-overhaul.mod" \
  http://127.0.0.1:8002/api/v1/command/mod/install
cd web && CWS_SMOKE_BASE_URL=http://localhost:5173 CWS_SMOKE_SKIP_WEBSERVER=1 \
  CWS_E2E_BACKEND_BASE=http://127.0.0.1:8002 \
  npx playwright test release-screenshots.spec.ts --workers=1
```

## Manual visual checklist questions

For each screenshot, ask:
1. Is the UI legible (font sizes, contrast, no overlap)?
2. Are warnings + destructive copy clear?
3. Do panels avoid blocking the main game flow?
4. Is the screenshot archived under `docs/release-artifacts/v1.0/screenshots/`?

## Screenshots

| # | File | What it shows | Milestone | Key commit | PR |
|---|---|---|---|---|---|
| 01 | [01-splash.png](screenshots/01-splash.png) | Splash screen — "AI 修仙世界模拟器" title + 5 menu buttons (开始 / 加载 / 设置 / 关于 / 退出) | baseline UI | n/a | n/a |
| 02 | [02-scenario-picker.png](screenshots/02-scenario-picker.png) | New-game form → Scenario picker expanded with **默认游戏**, **六朝纪事**, **Stage 1 Sample**, **三国仙纪**, **E2E Test Scenario** options | v0.5 | [stage-2d / v0.5 series](https://github.com/walthack/cultivation-world-simulator/commits/feat/scenario-engine-v1.0) | PR #1, PR #4 |
| 03 | [03-scenario-overview.png](screenshots/03-scenario-overview.png) | Scenario badge (`六朝纪事`) clicked → ScenarioOverviewModal with metadata header, **已触发事件** / **未触发事件** Timeline sections | Milestone B / v0.3 | `1693…` (Milestone B series) | PR #2 |
| 04 | [04-scenario-browser.png](screenshots/04-scenario-browser.png) | ScenarioBrowserModal — **Installed / Downloaded / Updates** tabs + **Create Scenario** + **Import…** buttons + installed scenario card | v0.5 | [v0.5 commits](https://github.com/walthack/cultivation-world-simulator/commits/feat/scenario-engine-v1.0) | PR #4 |
| 05a | [05a-wizard-step1-basics.png](screenshots/05a-wizard-step1-basics.png) | ScenarioWizardModal step 1 — Basics form (scenario id / title / version / author / description / tags / Start from Template) | v0.7 | `97fe329a` ScenarioWizardModal + composable + store + 6-step flow | PR #6 |
| 05b | [05b-wizard-step6-review.png](screenshots/05b-wizard-step6-review.png) | ScenarioWizardModal step 6 — Review (summary fields + raw JSON preview + Save & Activate / Export .zip) | v0.7 | `97fe329a` | PR #6 |
| 06 | [06-repository-fingerprint.png](screenshots/06-repository-fingerprint.png) | Installed scenario card shows status chip + verification badge (`○ unsigned`) + short fingerprint (`94b66977`) — proves the v0.9 fingerprint surface | v0.9 | `8902cf0d` scenario_fingerprint module + `2e23680d` frontend repository tabs | PR #8 |
| 07 | [07-runtime-control-hot-swap.png](screenshots/07-runtime-control-hot-swap.png) | advanced_runtime_control ON → Scenario Overview shows Activate buttons + Activate Confirm dialog with verbatim "**Hot-swap does not re-anchor time. Events scheduled before the current world time will not fire.**" | v0.8 | `fc214757` backend runtime + `0bae9d61` frontend Debug tab + Activate flow | PR #7 |
| 08 | [08-mod-manager-disabled.png](screenshots/08-mod-manager-disabled.png) | Mod Manager → Installed mods → **Sample Overhaul** card with `Python hooks: disabled` badge + extension chips + Enabled checkbox | v1.0 | `87f1a5bd` ModManagerModal + Settings toggle + locales + menu entry | PR #9 |
| 09 | [09-python-trust-warning.png](screenshots/09-python-trust-warning.png) | Settings panel → `Allow trusted Python mods` toggle clicked → Trust Warning modal with verbatim "**You are about to enable Python mod execution. Untrusted mods can do anything the game can do. Continue?**" + Cancel / Continue buttons | v1.0 | `87f1a5bd` + `8ad94460` backend `allow_trusted_python_mods` setting | PR #9 |
| 10 | [10-mod-manager-enabled.png](screenshots/10-mod-manager-enabled.png) | After confirming the trust gate → Mod Manager card flips to `Python hooks: enabled` (same Sample Overhaul card, badge now in the active style) | v1.0 | `fb05ff10` engine DSL registry + Python hooks gate integration | PR #9 |

## Aggregate verification cross-references

- Engineering RC results (pytest / vitest / boot smoke / Playwright Layer 3 + 4): see `docs/release-verification-report.md`
- Layer 3 spec (mod platform Python gate): `web/e2e/layer3-mod-platform.spec.ts`
- Layer 4A spec (scenario engine happy path): `web/e2e/layer4-scenario-engine.spec.ts`
- Layer 4 LLM spec (auto-skipped without key): `web/e2e/layer4-llm-authoring.spec.ts`
- This screenshot pack spec: `web/e2e/release-screenshots.spec.ts`
- v1.0 ADRs: `docs/adr/ADR-020`–`023`
