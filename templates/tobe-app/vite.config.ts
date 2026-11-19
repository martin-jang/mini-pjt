// 고정 템플릿 (Legacy2Next). react-router v7+ 에서 react-router-dom 은 react-router 와 같으므로
// 생성 코드가 습관적으로 react-router-dom 을 import 해도 빌드되도록 별칭을 둡니다.
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { 'react-router-dom': 'react-router' } },
})
