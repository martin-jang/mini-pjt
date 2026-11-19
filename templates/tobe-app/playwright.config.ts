// 흐름 검증용 Playwright 설정. vite preview(프로덕션 빌드) + MSW 활성 상태로 실행합니다.
// 포트는 Verifier가 빈 포트를 골라 PREVIEW_PORT로 넘깁니다.
import { defineConfig } from '@playwright/test'

const port = Number(process.env.PREVIEW_PORT ?? 4173)

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  reporter: [['json', { outputFile: 'e2e-results.json' }], ['line']],
  use: { baseURL: `http://127.0.0.1:${port}` },
  webServer: {
    command: `npx vite preview --host 127.0.0.1 --port ${port} --strictPort`,
    url: `http://127.0.0.1:${port}`,
    timeout: 60_000,
    reuseExistingServer: false,
  },
})
