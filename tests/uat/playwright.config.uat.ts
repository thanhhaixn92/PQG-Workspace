import { defineConfig, devices } from '@playwright/test';
import { join } from 'path';

export default defineConfig({
  testDir: join(__dirname),
  fullyParallel: false, // Run sequentially to avoid race conditions
  forbidOnly: !!process.env.CI,
  retries: 0, // No retries for UAT - fail fast
  workers: 1, // Single worker for deterministic results
  reporter: [
    ['line', { printSteps: true }],
    ['html', { outputFolder: join(__dirname, 'uat', 'artifacts', 'report'), open: 'never' }]
  ],
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 15000,
    navigationTimeout: 30000,
  },
  projects: [
    {
      name: 'chromium-uat',
      use: {
        ...devices['Desktop Chrome'],
        // Isolated context per test
        launchOptions: {
          args: [
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process',
            '--no-first-run',
            '--no-default-browser-check',
          ]
        }
      },
    },
  ],
  webServer: {
    command: 'cd frontend && npm run dev -- --host 127.0.0.1 --port 5173',
    url: 'http://127.0.0.1:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 60000,
    env: {
      NODE_ENV: 'test'
    }
  },
  expect: {
    timeout: 10000,
  },
  outputDir: join(__dirname, 'uat', 'artifacts', 'test-results'),
});