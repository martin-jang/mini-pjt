// 고정 템플릿: 라우터 껍데기. 실제 라우트는 생성되는 routes.tsx가 채웁니다.
import { BrowserRouter, Route, Routes } from 'react-router'
import { routes } from './routes'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {routes.map((r) => (
          <Route key={r.path} path={r.path} element={r.element} />
        ))}
      </Routes>
    </BrowserRouter>
  )
}
