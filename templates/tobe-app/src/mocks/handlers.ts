// 생성 시 결정적으로 덮어쓰는 MSW 핸들러 파일입니다 (LLM 작성 금지). 교육용 더미 데이터입니다.
import { http, HttpResponse } from 'msw'

export const handlers = [
  http.get('/api/sample', () => HttpResponse.json({ message: 'MSW 동작 확인' })),
]
