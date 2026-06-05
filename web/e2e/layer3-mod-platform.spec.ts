/**
 * Layer 3 — v1.0 Python hooks safety gate double-state Playwright test.
 *
 * UI entry path (verified 2026-06-04 via screenshot iteration):
 *   Splash screen ("AI 修仙世界模拟器") → click "设置" / "Settings" button →
 *   SystemMenu modal opens with defaultTab='settings'. From there:
 *     - Settings tab: data-testid="python-mod-switch" toggles the gate; click
 *       opens an inline trust-warning modal (.trust-modal with "Continue" /
 *       "Cancel" buttons) when flipping OFF → ON.
 *     - Mod Manager tab: click the SystemMenuShell tab button labelled
 *       "Mod 管理" / "Mod Manager"; ModManagerModal renders mod cards with a
 *       `.python-badge` element showing "Python hooks: enabled" or
 *       "Python hooks: disabled".
 *
 * Tests run serially (test.describe.serial) because they share a single
 * backend process and would otherwise race on allow_trusted_python_mods.
 *
 * Prerequisites:
 *   - Backend on 8002 with isolated CWS_DATA_DIR. Sample mod auto-loads from
 *     examples/mods/sample-overhaul/ when the data dir starts empty.
 *   - Vite dev server on 5173 (or `npm run preview` on 4173).
 *
 * Run:
 *   CWS_DATA_DIR=/tmp/cws-e2e-data CWS_NO_BROWSER=1 .venv/bin/python src/server/main.py --dev
 *   cd web && CWS_SMOKE_BASE_URL=http://localhost:5173 CWS_SMOKE_SKIP_WEBSERVER=1 \
 *     CWS_E2E_BACKEND_BASE=http://127.0.0.1:8002 CWS_E2E_ARTIFACTS=full \
 *     npx playwright test layer3-mod-platform.spec.ts
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

async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BACKEND_BASE}${path}`, init)
  if (!res.ok) {
    throw new Error(`API ${path} → ${res.status}`)
  }
  return res.json() as Promise<T>
}

async function setAdvancedPythonMods(enabled: boolean) {
  await api('/api/settings', {
    method: 'PATCH',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ allow_trusted_python_mods: enabled }),
  })
}

async function openSystemMenuFromSplash(page: Page) {
  await page.goto('/')
  // Splash menu buttons take a moment to mount after settings hydration.
  const settingsBtn = page.getByRole('button', { name: /设置|Settings/ }).first()
  await expect(settingsBtn).toBeVisible({ timeout: 15000 })
  await settingsBtn.click()
  // SystemMenu mounted: the Mod 管理 tab button is always present in the shell.
  await expect(page.getByRole('button', { name: /Mod 管理|Mod Manager/ })).toBeVisible({
    timeout: 10000,
  })
}

async function switchToModsTab(page: Page) {
  await page.getByRole('button', { name: /Mod 管理|Mod Manager/ }).click()
  // Mod Manager header anchors the panel; sample-overhaul card follows.
  await expect(page.getByRole('heading', { name: /Mod Manager/i })).toBeVisible({
    timeout: 10000,
  })
  await expect(page.getByText('Sample Overhaul').first()).toBeVisible({ timeout: 10000 })
}

test.describe.serial('Layer 3 — Python hooks safety gate', () => {
  test.beforeAll(async () => {
    // Sanity: backend reachable + sample-overhaul mod present
    const mods = await api<{ ok: boolean; data: { mods: any[] } }>(
      '/api/v1/query/mods/installed',
    )
    expect(mods.ok).toBe(true)
    const sample = mods.data.mods.find((m) => m.mod_id === 'sample-overhaul')
    expect(sample, 'sample-overhaul mod must be present before running e2e').toBeTruthy()
  })

  test.beforeEach(async () => {
    await setAdvancedPythonMods(false)
  })

  test.afterAll(async () => {
    await setAdvancedPythonMods(false)
  })

  test('default OFF — Mod Manager shows "Python hooks: disabled" badge for sample-overhaul', async ({
    page,
  }) => {
    await openSystemMenuFromSplash(page)
    await switchToModsTab(page)

    const badge = page.locator('.python-badge').filter({ hasText: /Python hooks: disabled/i }).first()
    await expect(badge).toBeVisible({ timeout: 10000 })
    // And the enabled variant is NOT visible
    await expect(page.locator('.python-badge.enabled')).toHaveCount(0)
  })

  test('default OFF — data-only extensions (asset/LLM/locale) still listed as active', async ({
    page,
  }) => {
    await openSystemMenuFromSplash(page)
    await switchToModsTab(page)

    // Extension chips on the sample-overhaul card use prefix:name form.
    await expect(page.getByText(/asset:portraits\/sample-male\.png/i)).toBeVisible({
      timeout: 10000,
    })
    await expect(page.getByText(/llm:sample_npc_action/i)).toBeVisible()
    await expect(page.getByText(/locale:en-US/i)).toBeVisible()

    // API sanity: data-only paths are active regardless of toggle
    const active = await api<{ ok: boolean; data: { extensions: ExtensionDTO[] } }>(
      '/api/v1/query/mods/extensions-active',
    )
    expect(active.ok).toBe(true)
    const assetExt = active.data.extensions.find(
      (e) => e.kind === 'asset' && e.name === 'portraits/sample-male.png',
    )
    expect(assetExt?.active).toBe(true)
    expect(assetExt?.inert).toBe(false)
  })

  test('default OFF — API reports sample_predicate as inert (gate blocking)', async () => {
    const active = await api<{ ok: boolean; data: { extensions: ExtensionDTO[] } }>(
      '/api/v1/query/mods/extensions-active',
    )
    const samplePred = active.data.extensions.find(
      (e) => e.kind === 'predicate' && e.name === 'sample_predicate',
    )
    expect(samplePred, 'sample_predicate extension must be declared').toBeDefined()
    expect(samplePred!.active).toBe(false)
    expect(samplePred!.inert).toBe(true)
  })

  test('toggle ON shows trust warning modal then enables Python hooks badge', async ({
    page,
  }) => {
    await openSystemMenuFromSplash(page)
    // Stay on the settings tab (default when opened via splash settings).
    const toggle = page.getByTestId('python-mod-switch')
    await expect(toggle).toBeVisible({ timeout: 10000 })
    await toggle.click()

    // Trust warning modal: literal copy is "Untrusted mods can do anything..."
    const trustModal = page.locator('.trust-modal')
    await expect(trustModal).toBeVisible({ timeout: 5000 })
    await expect(trustModal).toContainText(/Untrusted mods can do anything/i)

    await trustModal.getByRole('button', { name: /Continue/i }).click()

    // Wait briefly for PATCH round-trip + load_enabled_mods to settle.
    await page.waitForTimeout(500)

    // Switch to Mod Manager tab; badge should now read "enabled".
    await switchToModsTab(page)
    const badge = page.locator('.python-badge').filter({ hasText: /Python hooks: enabled/i }).first()
    await expect(badge).toBeVisible({ timeout: 10000 })
    await expect(badge).toHaveClass(/enabled/)
  })

  test('toggle ON — API reports sample_predicate as active (gate released)', async () => {
    await setAdvancedPythonMods(true)
    // PATCH path runs sync_advanced_runtime_control → load_enabled_mods
    // synchronously; small wait is defensive for HTTP round-trip only.
    await new Promise((resolve) => setTimeout(resolve, 200))

    const active = await api<{ ok: boolean; data: { extensions: ExtensionDTO[] } }>(
      '/api/v1/query/mods/extensions-active',
    )
    const samplePred = active.data.extensions.find(
      (e) => e.kind === 'predicate' && e.name === 'sample_predicate',
    )
    expect(samplePred, 'sample_predicate extension must be declared').toBeDefined()
    expect(samplePred!.active).toBe(true)
    expect(samplePred!.inert).toBe(false)
  })

  test('toggle OFF after enabling — Python hooks badge returns to disabled', async ({
    page,
  }) => {
    // Pre-condition: enable via API.
    await setAdvancedPythonMods(true)
    await new Promise((resolve) => setTimeout(resolve, 200))

    await openSystemMenuFromSplash(page)
    const toggle = page.getByTestId('python-mod-switch')
    await expect(toggle).toBeVisible({ timeout: 10000 })
    // Disabling the gate does not show a confirmation modal (safety gate only
    // guards the OFF→ON transition).
    await toggle.click()
    await page.waitForTimeout(500)

    await switchToModsTab(page)
    const badge = page.locator('.python-badge').filter({ hasText: /Python hooks: disabled/i }).first()
    await expect(badge).toBeVisible({ timeout: 10000 })

    // API confirms predicate de-registered (back to inert state).
    const active = await api<{ ok: boolean; data: { extensions: ExtensionDTO[] } }>(
      '/api/v1/query/mods/extensions-active',
    )
    const samplePred = active.data.extensions.find(
      (e) => e.kind === 'predicate' && e.name === 'sample_predicate',
    )
    expect(samplePred, 'sample_predicate extension must be declared').toBeDefined()
    expect(samplePred!.active).toBe(false)
    expect(samplePred!.inert).toBe(true)
  })
})
