// 고정 템플릿 진입점 (Legacy2Next). 이 파일은 생성 시 수정하지 않습니다.
// VITE_ENABLE_MSW=true 이면 MSW로 API를 mock한 뒤 앱을 띄웁니다.
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ConfigProvider } from 'antd'
import App from './App'

async function enableMocking() {
  if (import.meta.env.VITE_ENABLE_MSW !== 'true') return
  const { worker } = await import('./mocks/browser')
  // MSW v3: onUnhandledRequest 옵션이 없어졌으므로 쓰지 않습니다.
  await worker.start({ quiet: true })
}

enableMocking().then(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <ConfigProvider>
        <App />
      </ConfigProvider>
    </StrictMode>,
  )
})
