import { defineConfig, devices } from '@playwright/test';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

// 실제 에이전트 서버(스텁 그래프)와 콘솔을 함께 띄워 전체 흐름을 검증한다.
// 실행 기록·체크포인트는 임시 폴더에 따로 둬서 개발용 logs/와 섞이지 않게 한다
const dataDir = join(tmpdir(), `l2n-e2e-${process.pid}`);
const agentUrl = 'http://127.0.0.1:8010';
const consoleUrl = 'http://localhost:5180';
const siteUrl = 'http://127.0.0.1:8766/';

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
      // 시험 사이트: G2(외부 링크·외부 리다이렉트), T07a(ID/PW 로그인·간편인증 영역)
      command: `"${resolve('../agent/.venv/Scripts/python.exe')}" tests/fixtures/site_server.py --port 8766`,
      cwd: '../agent',
      url: siteUrl,
      reuseExistingServer: false,
    },
    {
      command: `"${resolve('../agent/.venv/Scripts/python.exe')}" -m legacy2next --port 8010 --fake-llm --stub-step-ms 30 --output-root "${join(dataDir, 'next-pjt')}" --log-dir "${join(dataDir, 'logs')}" --checkpoint "${join(dataDir, 'cp.sqlite')}" --session-dir "${join(dataDir, 'sessions')}" --auth-headless --cors-origin ${consoleUrl}`,
      cwd: '../agent',
      url: `${agentUrl}/health`,
      reuseExistingServer: false,
      // T07a ID/PW 자동 로그인 시험용 계정 (시험 사이트 기본 계정, 실제 비밀값 아님)
      env: { SITE_IDPW_E2E_USERNAME: 'tester', SITE_IDPW_E2E_PASSWORD: 'fixture-pass-1234' },
    },
    {
      command: 'npx vite --port 5180 --strictPort',
      url: consoleUrl,
      reuseExistingServer: false,
      env: { VITE_AGENT_API_URL: agentUrl },
    },
  ],
});
