import { defineConfig, devices } from '@playwright/test';

const baseURL = process.env.DOCKER_INFRA_BASE_URL || 'http://127.0.0.1:3001';
const outputRoot = process.env.DOCKER_INFRA_E2E_OUTPUT_ROOT || '.runtime/e2e';
const startCommand = process.env.DOCKER_INFRA_E2E_START_CMD;

export default defineConfig({
  testDir: './tests/e2e/specs',
  fullyParallel: false,
  timeout: 30_000,
  expect: {
    timeout: 5_000,
  },
  outputDir: `${outputRoot}/test-results`,
  reporter: [
    ['list'],
    ['html', { outputFolder: `${outputRoot}/playwright-report`, open: 'never' }],
  ],
  use: {
    baseURL,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
    testIdAttribute: 'data-testid',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: startCommand
    ? {
        command: startCommand,
        url: baseURL,
        reuseExistingServer: true,
        timeout: 120_000,
      }
    : undefined,
});
