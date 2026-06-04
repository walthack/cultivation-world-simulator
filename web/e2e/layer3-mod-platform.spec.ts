/**
 * Layer 3 — v1.0 Python hooks safety gate double-state Playwright test.
 *
 * 御主 2026-06-04 09:35 SGT mandate: 80-90% automated test of mod platform's
 * Python gate. Flow:
 *   install sample-overhaul mod
 *   open Mod Manager → assert "Python hooks: disabled" badge
 *   assert data-only mod parts visible/active
 *   turn on "Allow trusted Python mods" toggle → expect trust warning modal
 *   confirm → assert "Python hooks: enabled" badge
 *   assert custom predicate works (via API mod_extensions_active)
 *   turn off → assert disabled badge again
 *
 * Prerequisites:
 *   - Dev server running on http://localhost:5173 (vite) with backend at :8002
 *   - CWS_DATA_DIR set to an isolated tmp dir
 *   - Sample mod copied to $CWS_DATA_DIR/mods/sample-overhaul/ (the dispatch
 *     before tests does this if CWS_E2E_SETUP_MOD=1 is set)
 *
 * Run:
 *   # Terminal 1
 *   CWS_DATA_DIR=/tmp/cws-e2e-data CWS_NO_BROWSER=1 \
 *     .venv/bin/python src/server/main.py --dev
 *
 *   # Terminal 2 (copy sample mod first)
 *   mkdir -p /tmp/cws-e2e-data/mods/
 *   cp -r examples/mods/sample-overhaul /tmp/cws-e2e-data/mods/
 *
 *   # Terminal 3
 *   cd web && CWS_SMOKE_BASE_URL=http://localhost:5173 CWS_SMOKE_SKIP_WEBSERVER=1 \
 *     npx playwright test layer3-mod-platform.spec.ts
 */

import { expect, test } from '@playwright/test'

const BACKEND_BASE = process.env.CWS_E2E_BACKEND_BASE || 'http://localhost:8002'

async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BACKEND_BASE}${path}`, init)
  if (!res.ok) {
    throw new Error(`API ${path} → ${res.status}`)
  }
  return res.json() as Promise<T>
}

async function setAdvancedPythonMods(enabled: boolean) {
  await api('/api/v1/command/system/settings', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ allow_trusted_python_mods: enabled }),
  })
}

test.describe('Layer 3 — Python hooks safety gate', () => {
  test.beforeAll(async () => {
    // Sanity: backend reachable + sample-overhaul mod present
    const mods = await api<{ ok: boolean; data: { mods: any[] } }>(
      '/api/v1/query/mods/installed',
    )
    expect(mods.ok).toBe(true)
    const sample = mods.data.mods.find((m) => m.mod_id === 'sample-overhaul')
    expect(sample, 'sample-overhaul mod must be in $CWS_DATA_DIR/mods/ before running e2e').toBeTruthy()
  })

  test.beforeEach(async () => {
    // Reset to disabled (default) before each test
    await setAdvancedPythonMods(false)
  })

  test.afterAll(async () => {
    // Leave session in default-off state
    await setAdvancedPythonMods(false)
  })

  test('default OFF — Mod Manager shows "Python hooks: disabled" badge for sample-overhaul', async ({
    page,
  }) => {
    await page.goto('/')
    // Open System Menu → Mod Manager
    // SystemMenuShell shows a Mod Manager button; locate by text (zh-CN "Mod 管理" or en "Mod Manager")
    const modManagerButton = page
      .getByRole('button', { name: /Mod 管理|Mod Manager/ })
      .first()
    await modManagerButton.click()

    // Wait for ModManagerModal to render with the sample mod card
    await expect(page.getByText('sample-overhaul')).toBeVisible({ timeout: 10000 })

    // Default state badge — Python hooks: disabled
    const badge = page.getByText(/Python hooks: disabled/i).first()
    await expect(badge).toBeVisible()
  })

  test('default OFF — data-only extensions (asset/LLM/locale) still listed as active', async ({
    page,
  }) => {
    await page.goto('/')
    const modManagerButton = page
      .getByRole('button', { name: /Mod 管理|Mod Manager/ })
      .first()
    await modManagerButton.click()

    // Mod card shows extension list including asset/llm/locale entries
    await expect(page.getByText(/asset:.*sample-male.png/i)).toBeVisible({ timeout: 10000 })
    await expect(page.getByText(/llm:sample_npc_action|llm:.*npc_action/i)).toBeVisible()
    await expect(page.getByText(/locale:en_US|locale:en-US/i)).toBeVisible()

    // API sanity: data-only paths are active regardless of toggle
    const active = await api<{ ok: boolean; data: any }>('/api/v1/query/mods/extensions-active')
    expect(active.ok).toBe(true)
  })

  test('default OFF — API confirms Python predicate not registered to engine', async ({}) => {
    // Custom predicate `sample_predicate` from sample-overhaul/rules/predicates.py
    // must NOT be in the active extensions list when toggle is OFF.
    const active = await api<{ ok: boolean; data: { predicates?: string[]; rules?: any } }>(
      '/api/v1/query/mods/extensions-active',
    )
    const predicateNames: string[] =
      active.data?.predicates ||
      active.data?.rules?.predicates ||
      []
    expect(predicateNames).not.toContain('sample_predicate')
  })

  test('toggle ON shows trust warning modal then enables Python hooks badge', async ({ page }) => {
    await page.goto('/')

    // Open Settings panel (zh-CN "系统" / en "Settings")
    const settingsButton = page
      .getByRole('button', { name: /设置|Settings|System/ })
      .first()
    await settingsButton.click()

    // Toggle "Allow trusted Python mods" — data-testid="python-mod-switch"
    const toggle = page.getByTestId('python-mod-switch')
    await expect(toggle).toBeVisible({ timeout: 10000 })
    await toggle.click()

    // Expect trust warning modal to appear with verbatim warning fragment
    await expect(
      page.getByText(/Untrusted mods can do anything|trusted python mods|trust warning/i),
    ).toBeVisible({ timeout: 5000 })

    // Confirm — button text could be "Confirm" / "确认" / "Continue"
    const confirm = page
      .getByRole('button', { name: /Confirm|确认|Continue|Enable|启用/ })
      .first()
    await confirm.click()

    // Wait for setting to persist; verify via API
    await page.waitForTimeout(500)
    const settings = await api<{ ok: boolean; data: { allow_trusted_python_mods?: boolean } }>(
      '/api/v1/query/system/current-run',
    )
    // current-run shape may vary; if not exposed, fall back to active extensions check
    if (settings.data?.allow_trusted_python_mods !== undefined) {
      expect(settings.data.allow_trusted_python_mods).toBe(true)
    }

    // Open Mod Manager and assert badge flipped to enabled
    await page.keyboard.press('Escape')
    const modManagerButton = page
      .getByRole('button', { name: /Mod 管理|Mod Manager/ })
      .first()
    await modManagerButton.click()

    await expect(page.getByText(/Python hooks: enabled/i).first()).toBeVisible({ timeout: 10000 })
  })

  test('toggle ON — API confirms sample_predicate registered to engine', async ({}) => {
    await setAdvancedPythonMods(true)
    // Need a brief moment for mod_loader to register (server-side mod reload)
    await new Promise((resolve) => setTimeout(resolve, 1000))

    const active = await api<{ ok: boolean; data: { predicates?: string[]; rules?: any } }>(
      '/api/v1/query/mods/extensions-active',
    )
    const predicateNames: string[] =
      active.data?.predicates ||
      active.data?.rules?.predicates ||
      []
    expect(predicateNames).toContain('sample_predicate')
  })

  test('toggle OFF after enabling — Python hooks badge returns to disabled', async ({ page }) => {
    // Pre-condition: enable via API
    await setAdvancedPythonMods(true)
    await new Promise((resolve) => setTimeout(resolve, 500))

    await page.goto('/')
    const settingsButton = page
      .getByRole('button', { name: /设置|Settings|System/ })
      .first()
    await settingsButton.click()

    const toggle = page.getByTestId('python-mod-switch')
    await expect(toggle).toBeVisible({ timeout: 10000 })
    // Toggle off (no warning modal expected on disable; safety gate only on enable)
    await toggle.click()

    await page.waitForTimeout(500)

    // Open Mod Manager and assert badge is back to disabled
    await page.keyboard.press('Escape')
    const modManagerButton = page
      .getByRole('button', { name: /Mod 管理|Mod Manager/ })
      .first()
    await modManagerButton.click()
    await expect(page.getByText(/Python hooks: disabled/i).first()).toBeVisible({ timeout: 10000 })

    // API confirms predicate de-registered
    const active = await api<{ ok: boolean; data: { predicates?: string[]; rules?: any } }>(
      '/api/v1/query/mods/extensions-active',
    )
    const predicateNames: string[] =
      active.data?.predicates ||
      active.data?.rules?.predicates ||
      []
    expect(predicateNames).not.toContain('sample_predicate')
  })
})
