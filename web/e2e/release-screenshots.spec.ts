/**
 * v1.0 Release Screenshot Pack — captures 11 fixed screenshots into
 * docs/release-artifacts/v1.0/screenshots/ to back the manual visual
 * checklist. Each shot proves a specific milestone deliverable.
 *
 * Prereq:
 *   - Backend on 8002 with isolated CWS_DATA_DIR
 *   - Vite on 5173 (or set CWS_SMOKE_BASE_URL)
 *   - Stub LLM profile written via PUT /api/settings/llm
 *   - Sample-overhaul mod pre-installed via /api/v1/command/mod/install
 *   - The shot spec installs an e2e_test scenario draft for repo shots
 *
 * Run:
 *   CWS_SMOKE_BASE_URL=http://localhost:5173 CWS_SMOKE_SKIP_WEBSERVER=1 \
 *     CWS_E2E_BACKEND_BASE=http://127.0.0.1:8002 \
 *     npx playwright test release-screenshots.spec.ts --workers=1
 */

import { expect, test, type Page } from '@playwright/test'
import * as path from 'node:path'
import { fileURLToPath } from 'node:url'

const BACKEND_BASE = process.env.CWS_E2E_BACKEND_BASE || 'http://localhost:8002'
const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const SHOTS_DIR = path.resolve(__dirname, '..', '..', 'docs', 'release-artifacts', 'v1.0', 'screenshots')

async function api<T = any>(p: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BACKEND_BASE}${p}`, init)
  if (!res.ok) throw new Error(`${p} → ${res.status}`)
  return res.json() as Promise<T>
}

async function configureStubLLM() {
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
  for (let i = 0; i < 30; i++) {
    const status = await api<{ data: { status: string } }>('/api/v1/query/runtime/status')
    if (status.data.status === 'ready') break
    await new Promise((r) => setTimeout(r, 500))
  }
  await new Promise((r) => setTimeout(r, 2000)) // settle world snapshot
}

async function installE2EDraft() {
  await fetch(`${BACKEND_BASE}/api/v1/command/scenario/save-draft`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      scenario: {
        schema_version: '0.1',
        scenario_id: 'e2e_test',
        title: 'E2E Test Scenario',
        version: '1.0',
        author: 'release-pack',
        description: 'Installed via release screenshot pack for repository proof.',
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
}

async function installWsFilter(page: Page) {
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
              /* not JSON */
            }
          },
          true,
        )
      }
    }
    ;(window as any).WebSocket = Wrapped
  })
}

async function shot(page: Page, filename: string) {
  await page.screenshot({ path: path.join(SHOTS_DIR, filename), fullPage: false })
}

test.describe.serial('Release Screenshot Pack — v1.0', () => {
  test.beforeAll(async () => {
    await configureStubLLM()
    await installE2EDraft()
  })

  test.beforeEach(async () => {
    await resetSettings()
    await resetGame()
  })

  test('01 — Splash Screen (主菜单)', async ({ page }) => {
    await installWsFilter(page)
    await page.goto('/')
    await expect(page.getByRole('button', { name: /开始游戏/ }).first()).toBeVisible({
      timeout: 15000,
    })
    await page.waitForTimeout(500) // let video frame settle
    await shot(page, '01-splash.png')
  })

  test('02 — Scenario Picker (liuchao/sanguo/default)', async ({ page }) => {
    await installWsFilter(page)
    await page.goto('/')
    await page.getByRole('button', { name: /开始游戏|Start Game/ }).first().click()
    const sceneSelect = page.locator('.scenario-picker .n-select').first()
    await expect(sceneSelect).toBeVisible({ timeout: 10000 })
    await sceneSelect.click()
    await expect(page.locator('.n-base-select-option').first()).toBeVisible({ timeout: 5000 })
    // Let the teleported dropdown panel paint before screenshot.
    await page.waitForTimeout(500)
    await shot(page, '02-scenario-picker.png')
  })

  test('03 — Scenario Overview (badge + triggered events + metadata)', async ({ page }) => {
    await installWsFilter(page)
    await startGameWithScenario('liuchao')
    await page.goto('/')
    await page.locator('.scenario-badge-title').filter({ hasText: /六朝纪事/ }).first().click()
    await expect(page.getByText('已触发事件').first()).toBeVisible({ timeout: 10000 })
    await shot(page, '03-scenario-overview.png')
  })

  test('04 — Scenario Browser (Installed tab)', async ({ page }) => {
    await installWsFilter(page)
    await page.goto('/')
    await page.getByRole('button', { name: /开始游戏|Start Game/ }).first().click()
    await page.getByRole('button', { name: /^Browse$/ }).first().click()
    await expect(page.locator('.scenario-browser-tabs').first()).toBeVisible({ timeout: 10000 })
    await page.waitForTimeout(500)
    await shot(page, '04-scenario-browser.png')
  })

  test('05a — Wizard Step 1 (Basics)', async ({ page }) => {
    await installWsFilter(page)
    await page.goto('/')
    await page.getByRole('button', { name: /开始游戏|Start Game/ }).first().click()
    await page.getByRole('button', { name: /^Browse$/ }).first().click()
    await page.getByRole('button', { name: /Create Scenario/ }).first().click()
    const stepNav = page.locator('.wizard-steps').first()
    await expect(stepNav).toBeVisible({ timeout: 10000 })
    // Step 1 = Basics is default selected on open.
    await shot(page, '05a-wizard-step1-basics.png')
  })

  test('05b — Wizard Step 6 (Review)', async ({ page }) => {
    await installWsFilter(page)
    await page.goto('/')
    await page.getByRole('button', { name: /开始游戏|Start Game/ }).first().click()
    await page.getByRole('button', { name: /^Browse$/ }).first().click()
    await page.getByRole('button', { name: /Create Scenario/ }).first().click()
    const stepNav = page.locator('.wizard-steps').first()
    await expect(stepNav).toBeVisible({ timeout: 10000 })
    await stepNav.locator('.wizard-step').nth(5).click()
    await expect(stepNav.locator('.wizard-step').nth(5)).toContainText('Review')
    await page.waitForTimeout(300)
    await shot(page, '05b-wizard-step6-review.png')
  })

  test('06 — Repository / Fingerprint (Installed scenarios)', async ({ page }) => {
    await installWsFilter(page)
    await installE2EDraft() // idempotent — ensure the card has a fingerprint to display
    await page.goto('/')
    await page.getByRole('button', { name: /开始游戏|Start Game/ }).first().click()
    await page.getByRole('button', { name: /^Browse$/ }).first().click()
    await expect(page.locator('.scenario-browser-tabs').first()).toBeVisible({ timeout: 10000 })
    // Installed tab is default; e2e_test card shows the short fingerprint chip.
    await expect(page.locator('.scenario-fingerprint').first()).toBeVisible({ timeout: 10000 })
    await page.waitForTimeout(500)
    await shot(page, '06-repository-fingerprint.png')
  })

  test('07 — Runtime Control (Advanced + Hot-swap Warning)', async ({ page }) => {
    await installWsFilter(page)
    await startGameWithScenario('liuchao')
    await api('/api/settings', {
      method: 'PATCH',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ advanced_runtime_control: true }),
    })
    await page.goto('/')
    await page.locator('.scenario-badge-title').filter({ hasText: /六朝纪事/ }).first().click()
    const scenarioSelect = page.locator('.scenario-select').first()
    await expect(scenarioSelect).toBeVisible({ timeout: 10000 })
    await scenarioSelect.click()
    await page
      .locator('.n-base-select-option')
      .filter({ hasText: /三国仙纪|sanguo/i })
      .first()
      .click()
    await page.getByRole('button', { name: /Activate hot-swap/i }).click()
    // Activate Confirm is a separate n-modal (teleported); wait for the
    // dialog title to be present so the layered modal renders above the
    // overview before the screenshot.
    await expect(
      page.locator('.n-dialog').filter({ hasText: /Activate scenario/i }).first(),
    ).toBeVisible({ timeout: 10000 })
    await expect(
      page.getByText(/Hot-swap does not re-anchor time/),
    ).toBeVisible({ timeout: 5000 })
    await page.waitForTimeout(400)
    await shot(page, '07-runtime-control-hot-swap.png')
  })

  test('08 — Mod Manager (Python hooks: disabled)', async ({ page }) => {
    await installWsFilter(page)
    await page.goto('/')
    await page.getByRole('button', { name: /设置|Settings/ }).first().click()
    await page.getByRole('button', { name: /Mod 管理|Mod Manager/ }).click()
    await expect(page.getByText('Sample Overhaul').first()).toBeVisible({ timeout: 10000 })
    await expect(
      page.locator('.python-badge').filter({ hasText: /Python hooks: disabled/i }).first(),
    ).toBeVisible({ timeout: 10000 })
    await shot(page, '08-mod-manager-disabled.png')
  })

  test('09 — Python Trust Warning (Allow trusted Python mods)', async ({ page }) => {
    await installWsFilter(page)
    await page.goto('/')
    await page.getByRole('button', { name: /设置|Settings/ }).first().click()
    // Default tab is settings when entered via splash settings; toggle directly.
    const toggle = page.getByTestId('python-mod-switch')
    await expect(toggle).toBeVisible({ timeout: 10000 })
    await toggle.click()
    await expect(page.locator('.trust-modal')).toBeVisible({ timeout: 5000 })
    await expect(page.locator('.trust-modal')).toContainText(/Untrusted mods can do anything/i)
    await shot(page, '09-python-trust-warning.png')
  })

  test('10 — Mod Manager (Python hooks: enabled)', async ({ page }) => {
    await installWsFilter(page)
    await api('/api/settings', {
      method: 'PATCH',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ allow_trusted_python_mods: true }),
    })
    await new Promise((r) => setTimeout(r, 300))
    await page.goto('/')
    await page.getByRole('button', { name: /设置|Settings/ }).first().click()
    await page.getByRole('button', { name: /Mod 管理|Mod Manager/ }).click()
    await expect(page.getByText('Sample Overhaul').first()).toBeVisible({ timeout: 10000 })
    await expect(
      page.locator('.python-badge').filter({ hasText: /Python hooks: enabled/i }).first(),
    ).toBeVisible({ timeout: 10000 })
    await shot(page, '10-mod-manager-enabled.png')
  })
})
