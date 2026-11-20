import { defineConfig, devices } from '@playwright/test';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

// 실제 에이전트 서버(스텁 그래프)와 콘솔을 함께 띄워 전체 흐름을 검증한다.
// 실행 기록·체크포인트는 임시 폴더에 따로 둬서 개발용 logs/와 섞이지 않게 한다
const dataDir = join(tmpdir(), `l2n-e2e-${process.pid}`);
const agentUrl = 'http://127.0.0.1:8010';
const consoleUrl = 'http://localhost:5180';

export default defineConfig({
  testDir: './e2e-real',
  timeout: 60_000,
  workers: 1,
  use: {
    baseURL: consoleUrl,
    ...devices['Desktop Chrome'],
    viewport: { width: 1440, height: 900 },
  },
  webServer: [
    {
      command: `"${resolve('../agent/.venv/Scripts/python.exe')}" -m legacy2next --port 8010 --stub-step-ms 30 --log-dir "${join(dataDir, 'logs')}" --checkpoint "${join(dataDir, 'cp.sqlite')}" --cors-origin ${consoleUrl}`,
      cwd: '../agent',
      url: `${agentUrl}/health`,
      reuseExistingServer: false,
    },
    {
      command: 'npx vite --port 5180 --strictPort',
      url: consoleUrl,
      reuseExistingServer: false,
      env: { VITE_AGENT_API_URL: agentUrl },
    },
  ],
});
