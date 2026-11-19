// 고정 템플릿: MSW 브라우저 워커. 생성 시 수정하지 않습니다.
import { setupWorker } from 'msw/browser'
import { handlers } from './handlers'

export const worker = setupWorker(...handlers)
