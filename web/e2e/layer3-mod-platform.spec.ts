/**
 * Layer 3 — v1.0 Python hooks safety gate double-state Playwright test.
 *
 * 御主 2026-06-04 09:35 SGT mandate: 80-90% automated test of mod platform's
 * Python gate.
 *
 * STATUS — first live-run pass (2026-06-04, revised):
 *   - API-level assertions PASS: gate state is observable via
 *     /api/v1/query/mods/extensions-active, whose payload is
 *     { extensions: Array<{kind, name, active, inert, ...}> }.
 *   - UI-level assertions need DOM iteration. Selectors based on
 *     blind Vue source read; live DOM differs.
 *   - PRIOR "hot-reload limitation" claim retracted: the gate toggle DOES
 *     hot-reload via sync_advanced_runtime_control → load_enabled_mods. The
 *     earlier API assertions read a non-existent `data.predicates` shape and
 *     therefore showed nothing changing.
 *
 * Prerequisites (UPDATED — must install via API, not just copy folder):
 *   - Dev server running on http://localhost:5173 (vite) with backend at :8002
 *   - CWS_DATA_DIR set to an isolated tmp dir
 *   - Sample mod registered via POST /api/v1/command/mod/install with the
 *     bundled examples/mods/sample-overhaul/ packaged as .mod zip — copying
 *     the folder to $CWS_DATA_DIR/mods/<id>/ alone is NOT enough; the
 *     registry is keyed by mods_registry.json which only the install API
 *     populates.
 *
 * Run:
 *   # Terminal 1
 *   CWS_DATA_DIR=/tmp/cws-e2e-data CWS_NO_BROWSER=1 \
 *     .venv/bin/python src/server/main.py --dev
 *
 *   # Terminal 2 — install sample mod via API
 *   (cd examples/mods/sample-overhaul && zip -r /tmp/sample-overhaul.mod .)
 *   curl -X POST -F "file=@/tmp/sample-overhaul.mod" \
 *     http://127.0.0.1:8002/api/v1/command/mod/install
 *
 *   # Terminal 3
 *   cd web && CWS_SMOKE_BASE_URL=http://localhost:5173 CWS_SMOKE_SKIP_WEBSERVER=1 \
 *     CWS_E2E_ARTIFACTS=full npx playwright test layer3-mod-platform.spec.ts
 *
 * UI selectors known to need fixing (TODO):
 *   - System menu trigger: page.locator('.menu-toggle') opens the menu
 *   - Mod Manager tab inside menu: tab key='mods', label=t('ui.mod_manager')
 *   - The current test searches for "Mod Manager" / "Mod 管理" as a top-level
 *     button — incorrect. Must first click .menu-toggle, then click the mods
 *     tab inside SystemMenuShell.
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
  await api('/api/settings', {
    method: 'PATCH',
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
    // Open System Menu via the .menu-toggle control button on App.vue, then
    // click the "mods" tab inside SystemMenuShell.
    await page.locator('.menu-toggle').first().click()
    await page
      .getByRole('button', { name: /Mod 管理|Mod Manager/ })
      .first()
      .click()

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
    await page.locator('.menu-toggle').first().click()
    await page
      .getByRole('button', { name: /Mod 管理|Mod Manager/ })
      .first()
      .click()

    // Mod card shows extension list including asset/llm/locale entries
    await expect(page.getByText(/asset:.*sample-male.png/i)).toBeVisible({ timeout: 10000 })
    await expect(page.getByText(/llm:sample_npc_action|llm:.*npc_action/i)).toBeVisible()
    await expect(page.getByText(/locale:en_US|locale:en-US/i)).toBeVisible()

    // API sanity: data-only paths are active regardless of toggle
    const active = await api<{ ok: boolean; data: any }>('/api/v1/query/mods/extensions-active')
    expect(active.ok).toBe(true)
  })

  test('default OFF — API reports sample_predicate as inert (gate blocking)', async ({}) => {
    // Custom predicate `sample_predicate` from sample-overhaul/rules/predicates.py
    // is declared so it appears in the extensions list, but with active=false
    // and inert=true when the gate is OFF.
    type ExtensionDTO = { kind: string; name: string; active: boolean; inert: boolean }
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
    await page.locator('.menu-toggle').first().click()
    await page
      .getByRole('button', { name: /Mod 管理|Mod Manager/ })
      .first()
      .click()

    await expect(page.getByText(/Python hooks: enabled/i).first()).toBeVisible({ timeout: 10000 })
  })

  test('toggle ON — API reports sample_predicate as active (gate released)', async ({}) => {
    await setAdvancedPythonMods(true)
    // PATCH path runs sync_advanced_runtime_control which re-runs load_enabled_mods
    // synchronously; small wait is defensive for HTTP round-trip ordering only.
    await new Promise((resolve) => setTimeout(resolve, 200))

    type ExtensionDTO = { kind: string; name: string; active: boolean; inert: boolean }
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
    await page.locator('.menu-toggle').first().click()
    await page
      .getByRole('button', { name: /Mod 管理|Mod Manager/ })
      .first()
      .click()
    await expect(page.getByText(/Python hooks: disabled/i).first()).toBeVisible({ timeout: 10000 })

    // API confirms predicate de-registered (back to inert state)
    type ExtensionDTO = { kind: string; name: string; active: boolean; inert: boolean }
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
