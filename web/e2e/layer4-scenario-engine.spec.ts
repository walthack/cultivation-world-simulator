/**
 * Layer 4A — End-to-end Scenario Engine happy path (non-LLM).
 *
 * Covers the 8 milestone integrations:
 *   1+2. new game with liuchao → scenario badge visible
 *   3.   click badge → ScenarioOverviewModal shows triggered/未触发 sections
 *   4.   advanced runtime control ON → hot-swap warning text appears
 *   5.   save scenario draft via API → export the installed scenario zip
 *   6.   splash → 开始游戏 → ScenarioBrowserModal → Create Scenario → Wizard
 *        with 6 steps visible
 *   7.   repository endpoint returns the installed draft with shape
 *        { installed[], downloaded[], updates[] }
 *   8.   sample-overhaul mod present → Python gate OFF reflected in
 *        /api/v1/query/mods/extensions-active (data.extensions shape)
 *   9.   liuchao scripted avatars have distinct non-origin positions
 *        and non-unknown born regions
 *   10.  liuchao total avatar count equals scripted + generation profile
 *   11.  liuchao random NPC names use liuchao name_templates, not default
 *   12.  sanguo hot-swap name flip is skipped because hot-swap does not
 *        regenerate random NPCs in the current architecture
 *
 * Notes verified by screenshot iteration on 2026-06-05:
 *   - Tests must run serially because they share a single backend process.
 *   - The frontend auto-opens SystemMenu with the LLM tab (non-closable)
 *     when llm.profile is not configured. The beforeAll hook writes a stub
 *     LLM config so this auto-open does not intercept UI clicks.
 *   - Bundled scenarios (liuchao / sanguo / sample) live in
 *     /api/v1/query/scenarios and CANNOT be exported (contract:
 *     scenario_export_not_found). For an end-to-end export test we first
 *     install a custom scenario via /api/v1/command/scenario/save-draft.
 *   - `data.extensions` is the real shape returned by extensions-active
 *     (kind/name/active/inert/python_required). The previous spec read a
 *     non-existent `data.predicates` field.
 *
 * Prereq sample mod: package examples/mods/sample-overhaul/ and POST it to
 * /api/v1/command/mod/install before running this spec.
 *
 * Run:
 *   # Terminal 1 — fresh data dir, stub LLM
 *   rm -rf /tmp/cws-e2e-data && mkdir /tmp/cws-e2e-data
 *   CWS_DATA_DIR=/tmp/cws-e2e-data CWS_NO_BROWSER=1 \
 *     .venv/bin/python src/server/main.py --dev
 *
 *   # Terminal 2 — Vite or `npm run preview`
 *   cd web && npm run dev
 *
 *   # Terminal 3
 *   (cd examples/mods/sample-overhaul && zip -r /tmp/sample-overhaul.mod .)
 *   curl -X POST -F "file=@/tmp/sample-overhaul.mod" \
 *     http://127.0.0.1:8002/api/v1/command/mod/install
 *   cd web && CWS_SMOKE_BASE_URL=http://localhost:5173 CWS_SMOKE_SKIP_WEBSERVER=1 \
 *     CWS_E2E_BACKEND_BASE=http://127.0.0.1:8002 \
 *     npx playwright test layer4-scenario-engine.spec.ts --workers=1
 */

import { expect, test, type Page } from '@playwright/test'

const BACKEND_BASE = process.env.CWS_E2E_BACKEND_BASE || 'http://localhost:8002'

type ExtensionDTO = {
  kind: string
  name: string
  active: boolean
  inert: boolean
  python_required: boolean
}

type AvatarOverviewDTO = {
  id: string
  name: string
  x: number
  y: number
}

async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BACKEND_BASE}${path}`, init)
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`API ${path} → ${res.status}: ${body.slice(0, 200)}`)
  }
  return res.json() as Promise<T>
}

async function configureStubLLM() {
  // Write a dummy LLM profile so the splash/socket auto-open of the
  // non-closable LLM config menu doesn't intercept clicks in the tests.
  await fetch(`${BACKEND_BASE}/api/settings/llm`, {
    method: 'PUT',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      base_url: 'http://127.0.0.1:9999',
      api_key: 'sk-test-noop',
      model_name: 'noop',
      fast_model_name: 'noop',
      mode: 'default',
      max_concurrent_requests: 10,
      api_format: 'openai',
    }),
  })
}

async function resetSettings() {
  await api('/api/settings', {
    method: 'PATCH',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      advanced_runtime_control: false,
      allow_trusted_python_mods: false,
    }),
  })
}

async function resetGame() {
  // Idempotent: if no game running this still returns ok.
  await fetch(`${BACKEND_BASE}/api/v1/command/game/reset`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: '{}',
  })
}

async function startGameWithScenario(scenario_id: string) {
  await api('/api/v1/command/game/start', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      init_npc_num: 3,
      sect_num: 1,
      content_locale: 'zh-CN',
      scenario_id,
    }),
  })
  // Wait for status to settle to "ready" / "running"
  for (let i = 0; i < 30; i++) {
    const status = await api<{ ok: boolean; data: { status: string } }>(
      '/api/v1/query/runtime/status',
    )
    if (status.data.status === 'ready' || status.data.status === 'running') break
    await new Promise((r) => setTimeout(r, 500))
  }
}

async function installWsFilter(page: Page) {
  // The backend WebSocket emits an `llm_config_required` message when the
  // boot-time LLM connectivity check fails (our stub LLM URL is unreachable
  // by design — we only need the menu to NOT auto-open). The FE handler
  // opens a non-closable SystemMenu on the LLM tab, which intercepts every
  // subsequent click. Drop that one message at the WebSocket layer before
  // any application listener sees it.
  await page.addInitScript(() => {
    const Original = window.WebSocket
    class Wrapped extends Original {
      constructor(url: string | URL, protocols?: string | string[]) {
        super(url, protocols)
        this.addEventListener(
          'message',
          (event) => {
            try {
              const data = JSON.parse((event as MessageEvent).data)
              if (data && data.type === 'llm_config_required') {
                event.stopImmediatePropagation()
                event.stopPropagation()
              }
            } catch {
              /* not JSON — pass through */
            }
          },
          true,
        )
      }
    }
    ;(window as any).WebSocket = Wrapped
  })
}

async function gotoGameShell(page: Page) {
  await installWsFilter(page)
  await page.goto('/')
  // Game shell is keyed by `.scenario-badge-title` or any in-game control.
  await expect(page.locator('.scenario-badge-title').first()).toBeVisible({
    timeout: 15000,
  })
}

async function gotoSplash(page: Page) {
  await installWsFilter(page)
  await page.goto('/')
  // Splash exposes Settings/开始游戏 buttons inside its glass-panel menu.
  await expect(page.getByRole('button', { name: /开始游戏|Start Game/ }).first()).toBeVisible({
    timeout: 15000,
  })
}

test.describe.serial('Layer 4A — Scenario engine E2E happy path', () => {
  test.beforeAll(async () => {
    await configureStubLLM()
  })

  test.beforeEach(async () => {
    await resetSettings()
    await resetGame()
  })

  test('step 1+2: new game with liuchao → scenario badge visible', async ({ page }) => {
    await startGameWithScenario('liuchao')
    await gotoGameShell(page)
    await expect(page.locator('.scenario-badge-title').filter({ hasText: /六朝纪事/ }).first())
      .toBeVisible({ timeout: 15000 })
  })

  test('step 3: scenario panel — events grouped triggered vs upcoming', async ({ page }) => {
    await startGameWithScenario('liuchao')
    await gotoGameShell(page)

    await page.locator('.scenario-badge-title').filter({ hasText: /六朝纪事/ }).first().click()

    // ScenarioOverviewModal Timeline tab default — Chinese section headings.
    await expect(page.getByText('已触发事件').first()).toBeVisible({ timeout: 10000 })
    await expect(page.getByText('未触发事件').first()).toBeVisible()
  })

  test('step 4: advanced runtime control → hot-swap shows verbatim warning', async ({ page }) => {
    await startGameWithScenario('liuchao')
    await api('/api/settings', {
      method: 'PATCH',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ advanced_runtime_control: true }),
    })

    await gotoGameShell(page)
    await page.locator('.scenario-badge-title').filter({ hasText: /六朝纪事/ }).first().click()

    // Runtime-controls section appears with the scenario select + activate buttons.
    const scenarioSelect = page.locator('.scenario-select').first()
    await expect(scenarioSelect).toBeVisible({ timeout: 10000 })
    await scenarioSelect.click()
    // Naive Select dropdown renders options as .n-base-select-option in a
    // teleported layer; filter by visible text rather than role=option.
    await page
      .locator('.n-base-select-option')
      .filter({ hasText: /三国仙纪|sanguo/i })
      .first()
      .click()

    await page.getByRole('button', { name: /Activate hot-swap/i }).click()

    // Confirmation modal contains the verbatim hot-swap warning text.
    await expect(
      page.getByText(/Hot-swap does not re-anchor time\. Events scheduled before the current world time will not fire\./),
    ).toBeVisible({ timeout: 10000 })
  })

  test('step 5: scenario save-draft installs + export returns valid zip blob', async () => {
    // Bundled scenarios cannot be exported (contract: scenario_export_not_found).
    // For an end-to-end export test, first install a custom scenario via
    // /api/v1/command/scenario/save-draft, then export that one.
    const sampleScenario = await fetch(
      'data:application/json;base64,' +
        Buffer.from(
          JSON.stringify({
            schema_version: '0.1',
            scenario_id: 'e2e_test',
            title: 'E2E Test',
            version: '1.0',
            author: 'e2e',
            description: 'smoke',
            world_preset: { preset_id: 'default' },
            initial_state: {
              year: 1,
              month: 1,
              avatars: [
                {
                  id: 'e2e-avatar',
                  surname: '测',
                  given_name: '试',
                  gender: '男',
                  age: 28,
                  sect_id: null,
                  realm: 'QI_REFINEMENT',
                  stage: 'EARLY_STAGE',
                  level: 1,
                  persona_traits: ['RATIONAL'],
                  goldfinger_id: 'CHILD_OF_FORTUNE',
                  long_term_objective: 'E2E export smoke.',
                },
              ],
              sects: [],
              relationships: [],
              world_flags: {},
            },
          }),
        ).toString('base64'),
    )
      .then((r) => r.json())
      .catch(() => null)
    expect(sampleScenario).toBeTruthy()

    const saveRes = await fetch(`${BACKEND_BASE}/api/v1/command/scenario/save-draft`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        scenario: sampleScenario,
        timeline: { schema_version: '0.1', events: [] },
      }),
    })
    expect(saveRes.ok).toBe(true)

    const exportRes = await fetch(`${BACKEND_BASE}/api/v1/command/scenario/export`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ scenario_id: 'e2e_test' }),
    })
    expect(exportRes.status).toBe(200)
    expect(exportRes.headers.get('content-type')).toMatch(/zip|octet-stream/i)
    const blob = await exportRes.blob()
    expect(blob.size).toBeGreaterThan(200)
  })

  test('step 6: splash → Browse → Create Scenario → Wizard shows 6 steps', async ({ page }) => {
    await gotoSplash(page)
    // "开始游戏" opens SystemMenu start tab where the new-game form is rendered.
    await page.getByRole('button', { name: /开始游戏|Start Game/ }).first().click()
    // The new-game form has a Scenario picker with a small "Browse" text button.
    const browseButton = page.getByRole('button', { name: /^Browse$/ }).first()
    await expect(browseButton).toBeVisible({ timeout: 10000 })
    await browseButton.click()

    // ScenarioBrowserModal: click "Create Scenario" to open ScenarioWizardModal.
    await page.getByRole('button', { name: /Create Scenario/ }).first().click()

    // Wizard step nav lists 6 steps; assert the first and last to anchor.
    const stepNav = page.locator('.wizard-steps').first()
    await expect(stepNav).toBeVisible({ timeout: 10000 })
    await expect(stepNav.locator('.wizard-step').nth(0)).toContainText('Basics')
    await expect(stepNav.locator('.wizard-step').nth(5)).toContainText('Review')
    await expect(stepNav.locator('.wizard-step')).toHaveCount(6)
  })

  test('step 7: scenario/repository returns valid shape with installed draft', async () => {
    // Make sure the draft from step 5 is present (idempotent install).
    await fetch(`${BACKEND_BASE}/api/v1/command/scenario/save-draft`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        scenario: {
          schema_version: '0.1',
          scenario_id: 'e2e_test',
          title: 'E2E Test',
          version: '1.0',
          author: 'e2e',
          description: 'smoke',
          world_preset: { preset_id: 'default' },
          initial_state: {
            year: 1,
            month: 1,
            avatars: [],
            sects: [],
            relationships: [],
            world_flags: {},
          },
        },
        timeline: { schema_version: '0.1', events: [] },
      }),
    })

    const repo = await api<{
      ok: boolean
      data: {
        installed: Array<{ id: string; verification?: { status?: string } }>
        downloaded: Array<unknown>
        updates: Array<unknown>
      }
    }>('/api/v1/query/scenario/repository')

    expect(Array.isArray(repo.data.installed)).toBe(true)
    expect(Array.isArray(repo.data.downloaded)).toBe(true)
    expect(Array.isArray(repo.data.updates)).toBe(true)

    const installed = repo.data.installed.find((s) => s.id === 'e2e_test')
    expect(installed, 'e2e_test should be in repository installed list').toBeTruthy()
    if (installed?.verification?.status) {
      expect(['verified', 'modified', 'unsigned']).toContain(installed.verification.status)
    }
  })

  test('step 8: sample mod installed — Python gate default OFF reported via extensions API', async () => {
    const mods = await api<{ ok: boolean; data: { mods: Array<{ mod_id: string }> } }>(
      '/api/v1/query/mods/installed',
    )
    const sample = mods.data.mods.find((m) => m.mod_id === 'sample-overhaul')
    expect(
      sample,
      'sample-overhaul mod must be pre-installed; package and POST examples/mods/sample-overhaul/ before running',
    ).toBeTruthy()

    await api('/api/settings', {
      method: 'PATCH',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ allow_trusted_python_mods: false }),
    })
    await new Promise((r) => setTimeout(r, 300))

    const active = await api<{ ok: boolean; data: { extensions: ExtensionDTO[] } }>(
      '/api/v1/query/mods/extensions-active',
    )
    const samplePred = active.data.extensions.find(
      (e) => e.kind === 'predicate' && e.name === 'sample_predicate',
    )
    expect(samplePred, 'sample_predicate must be declared by sample-overhaul').toBeDefined()
    expect(samplePred!.active).toBe(false)
    expect(samplePred!.inert).toBe(true)
  })

  test('step 9: liuchao scripted avatars have placed runtime positions', async () => {
    await startGameWithScenario('liuchao')

    const overview = await api<{
      ok: boolean
      data: { avatars: AvatarOverviewDTO[] }
    }>('/api/v1/query/avatars/overview')

    const scriptedIds = ['cheng-zongyang', 'wang-zhe', 'xiao-zi']
    const scripted = scriptedIds.map((id) => overview.data.avatars.find((avatar) => avatar.id === id))
    for (const avatar of scripted) {
      expect(avatar, 'scripted avatar should exist in overview').toBeTruthy()
      expect([avatar!.x, avatar!.y], `${avatar!.id} should not remain at origin`).not.toEqual([0, 0])
    }

    const positions = new Set(scripted.map((avatar) => `${avatar!.x}:${avatar!.y}`))
    expect(positions.size, 'scripted avatars should not stack on one tile').toBe(scriptedIds.length)

    for (const id of scriptedIds) {
      const detail = await api<{
        ok: boolean
        data: { id: string; born_region_id: number | null }
      }>(`/api/v1/query/detail?type=avatar&id=${encodeURIComponent(id)}`)
      expect(detail.data.id).toBe(id)
      expect(detail.data.born_region_id, `${id} should have a born_region_id`).not.toBeNull()
      expect(detail.data.born_region_id, `${id} should have a known born_region_id`).not.toBe(-1)
    }
  })

  test('step 10: liuchao avatar count equals scripted plus profile random NPC count', async () => {
    await startGameWithScenario('liuchao')

    const overview = await api<{
      ok: boolean
      data: { avatar_count: number }
    }>('/api/v1/query/avatars/overview')

    expect(overview.data.avatar_count).toBe(6)
  })

  test('step 11: liuchao random NPC names use scenario name templates', async () => {
    await startGameWithScenario('liuchao')

    const overview = await api<{
      ok: boolean
      data: { avatars: AvatarOverviewDTO[] }
    }>('/api/v1/query/avatars/overview')

    const scriptedIds = new Set(['cheng-zongyang', 'wang-zhe', 'xiao-zi'])
    const randomNames = overview.data.avatars
      .filter((avatar) => !scriptedIds.has(avatar.id))
      .map((avatar) => avatar.name)

    expect(randomNames.length).toBeGreaterThan(0)
    expect(
      randomNames.some((name) => /^(程|王|紫|萧|秦)/.test(name)),
      `random names should include liuchao surnames; got ${randomNames.join(', ')}`,
    ).toBe(true)
    expect(
      randomNames.some((name) => /^(司马|慕容|上官|独孤|东方|南宫|西门|北冥|欧阳|夏侯|令狐|皇甫|公孙|轩辕)/.test(name)),
      `random names should not use distinctive default surnames; got ${randomNames.join(', ')}`,
    ).toBe(false)
  })

  test.skip(
    'step 12: hot-swap to sanguo flips generated NPC names',
    async () => {
      // Skipped intentionally: hot-swap replaces scripted scenario runtime state
      // but does not regenerate existing random NPCs, so there is no name pool
      // transition to assert until NPC regeneration is supported.
    },
  )
})
