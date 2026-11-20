import { defineConfig, devices } from '@playwright/test';

// 목업 진행 속도를 높여 전체 흐름을 빠르게 검증한다
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  use: {
    baseURL: 'http://localhost:5179',
    ...devices['Desktop Chrome'],
    viewport: { width: 1440, height: 900 },
  },
  webServer: {
    command: 'npx vite --port 5179 --strictPort',
    url: 'http://localhost:5179',
    reuseExistingServer: false,
    env: { VITE_MOCK_TICK_MS: '40' },
  },
});
