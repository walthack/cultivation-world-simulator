import { defineConfig, devices } from '@playwright/test'

const baseURL = process.env.CWS_SMOKE_BASE_URL || 'http://127.0.0.1:4173'
const skipWebServer = process.env.CWS_SMOKE_SKIP_WEBSERVER === '1'

// CWS_E2E_ARTIFACTS=full → always capture trace/screenshot/video (for release
// verification archive). Default: only on failure (CI / dev). Useful for
// generating the visual evidence needed by docs/release-verification-report.md.
const fullArtifacts = process.env.CWS_E2E_ARTIFACTS === 'full'

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: {
    timeout: 10_000,
  },
  fullyParallel: true,
  reporter: process.env.CI
    ? [['html', { open: 'never' }], ['list']]
    : fullArtifacts
      ? [['html', { open: 'never', outputFolder: 'playwright-report-artifacts' }], ['list']]
      : 'list',
  use: {
    baseURL,
    trace: fullArtifacts ? 'on' : 'retain-on-failure',
    screenshot: fullArtifacts ? 'on' : 'only-on-failure',
    video: fullArtifacts ? 'on' : 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: skipWebServer
    ? undefined
    : {
        command: 'npm run preview -- --host 127.0.0.1 --port 4173',
        url: baseURL,
        reuseExistingServer: !process.env.CI,
        timeout: 60_000,
      },
})
