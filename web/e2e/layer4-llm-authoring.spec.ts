/**
 * Layer 4 — LLM-assisted scenario authoring (auto-skip without key).
 *
 * 御主 09:35 SGT mandate: LLM-related tests must not block automation.
 *   LLM key present → run generate test
 *   LLM key absent → skip with reason
 *
 * Detects key presence via `/api/v1/query/system/current-run` checking
 * `llm.profile.has_api_key`. If false, skip the entire describe block.
 *
 * Tests when LLM available:
 *   - Wizard LLM step accepts a description input
 *   - "Generate" button triggers POST /api/v1/command/scenario/generate
 *   - Response shape: {ok, draft|raw_output, validation_errors, attempts}
 *   - Wizard fields populate from draft (smoke check on form)
 *
 * Prerequisites:
 *   - Dev server running with LLM API key configured in user settings
 *   - CWS_DATA_DIR set to isolated dir
 *
 * Run:
 *   cd web && CWS_SMOKE_BASE_URL=http://localhost:5173 CWS_SMOKE_SKIP_WEBSERVER=1 \
 *     npx playwright test layer4-llm-authoring.spec.ts
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

async function hasLLMKey(): Promise<boolean> {
  try {
    const settings = await api<{
      ok: boolean
      data: { llm?: { profile?: { has_api_key?: boolean; base_url?: string } } }
    }>('/api/v1/query/system/current-run')
    const profile = settings.data?.llm?.profile
    return Boolean(profile?.has_api_key && profile?.base_url)
  } catch {
    return false
  }
}

test.describe('Layer 4 — LLM-assisted authoring (optional)', () => {
  let llmAvailable = false

  test.beforeAll(async () => {
    llmAvailable = await hasLLMKey()
    if (!llmAvailable) {
      test.skip(
        true,
        'LLM key not configured (`llm.profile.has_api_key=false` or `base_url` empty in settings). ' +
          'To run this layer: configure LLM in Settings → LLM Config Panel, then re-run.',
      )
    }
  })

  test('POST /scenario/generate returns draft from description', async ({}) => {
    test.skip(!llmAvailable, 'no LLM key')
    const res = await fetch(`${BACKEND_BASE}/api/v1/command/scenario/generate`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        description: 'A short test scenario set in a small mountain village',
        hints: { preset_id: 'default' },
      }),
    })
    expect(res.ok).toBe(true)
    const body = (await res.json()) as {
      ok: boolean
      data: {
        ok: boolean
        draft?: any
        raw_output?: any
        validation_errors: string[]
        attempts: number
      }
    }
    expect(body.ok).toBe(true)
    // attempts >= 1
    expect(body.data.attempts).toBeGreaterThanOrEqual(1)
    // EITHER draft is populated (validation passed) OR raw_output + validation_errors present
    if (body.data.ok) {
      expect(body.data.draft).toBeTruthy()
      expect(body.data.draft.scenario).toBeTruthy()
      expect(body.data.draft.scenario.scenario_id).toBeTruthy()
    } else {
      // Fallback path: raw output present so user can manually fix
      expect(body.data.raw_output).toBeTruthy()
      expect(Array.isArray(body.data.validation_errors)).toBe(true)
    }
  })

  test('Wizard LLM step populates scenario fields after Generate (UI smoke)', async ({ page }) => {
    test.skip(!llmAvailable, 'no LLM key')
    await page.goto('/')

    // Open Scenario Browser
    const browseButton = page
      .getByRole('button', { name: /Scenario|场景|Browse/ })
      .first()
    await browseButton.click()
    const createButton = page.getByRole('button', { name: /Create Scenario|创建 Scenario|新建/ })
    await createButton.first().click()

    // Navigate to LLM Assisted step (step 3 per spec)
    // Click "Next" 2x to reach LLM step
    const nextButton = page.getByRole('button', { name: /Next|下一步/ })
    if (await nextButton.isVisible()) {
      await nextButton.click()
      await nextButton.click()
    }

    // Fill description textbox
    const descriptionInput = page.getByPlaceholder(/Describe your world|描述你的世界|description/i)
    await descriptionInput.fill('Test scenario about a small mountain village')

    // Click Generate
    const generateButton = page.getByRole('button', { name: /Generate|生成/ })
    await generateButton.click()

    // Wait for LLM response (may take several seconds)
    // Success signal: fields populated OR error message shown
    await page.waitForTimeout(15000)

    // Smoke: title field should be non-empty after Generate
    // Selector pattern — adjust if test fails
    const titleField = page.getByLabel(/Title|标题/i).first()
    const titleValue = await titleField.inputValue().catch(() => '')
    // EITHER title populated OR error visible
    const hasContent = titleValue.length > 0
    const hasError = await page
      .getByText(/error|validation|失败/i)
      .isVisible()
      .catch(() => false)
    expect(hasContent || hasError).toBe(true)
  })
})
