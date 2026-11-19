// 생성 시 Page Builder가 덮어쓰는 파일입니다. 템플릿에는 샘플 라우트만 있습니다.
import type { ReactElement } from 'react'
import SamplePage from './pages/SamplePage'

export interface AppRoute {
  path: string
  title: string
  element: ReactElement
}

export const routes: AppRoute[] = [{ path: '/', title: '샘플', element: <SamplePage /> }]
