// 교육용 더미 데이터입니다. 이 파일은 Legacy2Next가 결정적으로 생성합니다 (LLM 작성 금지).
import { http, HttpResponse } from 'msw'
import { listData, optionData } from './data'

export const handlers = [
  http.post('/api/auth/login', async ({ request }) => {
    const body = (await request.json()) as Record<string, string>
    if (!body.username || !body.password) {
      return HttpResponse.json({ ok: false, message: '아이디와 비밀번호를 입력하세요.' }, { status: 400 })
    }
    return HttpResponse.json({ ok: true, message: '로그인되었습니다.', user: body.username })
  }),
  http.get('/api/activity', () => HttpResponse.json(listData['activity'])),
  http.get('/api/billpay/options', () => HttpResponse.json(optionData['billpay'] ?? {})),
  http.post('/api/billpay', async ({ request }) => {
    const body = (await request.json()) as Record<string, string>
    const empty = Object.entries(body).filter(([, v]) => !String(v ?? '').trim()).map(([k]) => k)
    if (empty.length) {
      return HttpResponse.json({ ok: false, message: `입력이 필요합니다: ${empty.join(', ')}`, submitted: body }, { status: 400 })
    }
    return HttpResponse.json({ ok: true, message: '청구서 납부 처리가 완료되었습니다.', submitted: body })
  }),
  http.get('/api/findtrans', () => HttpResponse.json(listData['findtrans'])),
  http.get('/api/lookup/options', () => HttpResponse.json(optionData['lookup'] ?? {})),
  http.post('/api/lookup', async ({ request }) => {
    const body = (await request.json()) as Record<string, string>
    const empty = Object.entries(body).filter(([, v]) => !String(v ?? '').trim()).map(([k]) => k)
    if (empty.length) {
      return HttpResponse.json({ ok: false, message: `입력이 필요합니다: ${empty.join(', ')}`, submitted: body }, { status: 400 })
    }
    return HttpResponse.json({ ok: true, message: '로그인 정보 찾기 처리가 완료되었습니다.', submitted: body })
  }),
  http.get('/api/openaccount/options', () => HttpResponse.json(optionData['openaccount'] ?? {})),
  http.post('/api/openaccount', async ({ request }) => {
    const body = (await request.json()) as Record<string, string>
    const empty = Object.entries(body).filter(([, v]) => !String(v ?? '').trim()).map(([k]) => k)
    if (empty.length) {
      return HttpResponse.json({ ok: false, message: `입력이 필요합니다: ${empty.join(', ')}`, submitted: body }, { status: 400 })
    }
    return HttpResponse.json({ ok: true, message: '계좌 개설 처리가 완료되었습니다.', submitted: body })
  }),
  http.get('/api/overview', () => HttpResponse.json(listData['overview'])),
  http.get('/api/register/options', () => HttpResponse.json(optionData['register'] ?? {})),
  http.post('/api/register', async ({ request }) => {
    const body = (await request.json()) as Record<string, string>
    const empty = Object.entries(body).filter(([, v]) => !String(v ?? '').trim()).map(([k]) => k)
    if (empty.length) {
      return HttpResponse.json({ ok: false, message: `입력이 필요합니다: ${empty.join(', ')}`, submitted: body }, { status: 400 })
    }
    return HttpResponse.json({ ok: true, message: '회원 가입 처리가 완료되었습니다.', submitted: body })
  }),
  http.get('/api/requestloan/options', () => HttpResponse.json(optionData['requestloan'] ?? {})),
  http.post('/api/requestloan', async ({ request }) => {
    const body = (await request.json()) as Record<string, string>
    const empty = Object.entries(body).filter(([, v]) => !String(v ?? '').trim()).map(([k]) => k)
    if (empty.length) {
      return HttpResponse.json({ ok: false, message: `입력이 필요합니다: ${empty.join(', ')}`, submitted: body }, { status: 400 })
    }
    return HttpResponse.json({ ok: true, message: '대출 신청 처리가 완료되었습니다.', submitted: body })
  }),
  http.get('/api/transaction', () => HttpResponse.json(listData['transaction'])),
  http.get('/api/transfer/options', () => HttpResponse.json(optionData['transfer'] ?? {})),
  http.post('/api/transfer', async ({ request }) => {
    const body = (await request.json()) as Record<string, string>
    const empty = Object.entries(body).filter(([, v]) => !String(v ?? '').trim()).map(([k]) => k)
    if (empty.length) {
      return HttpResponse.json({ ok: false, message: `입력이 필요합니다: ${empty.join(', ')}`, submitted: body }, { status: 400 })
    }
    return HttpResponse.json({ ok: true, message: '자금 이체 처리가 완료되었습니다.', submitted: body })
  }),
  http.get('/api/updateprofile/options', () => HttpResponse.json(optionData['updateprofile'] ?? {})),
  http.post('/api/updateprofile', async ({ request }) => {
    const body = (await request.json()) as Record<string, string>
    const empty = Object.entries(body).filter(([, v]) => !String(v ?? '').trim()).map(([k]) => k)
    if (empty.length) {
      return HttpResponse.json({ ok: false, message: `입력이 필요합니다: ${empty.join(', ')}`, submitted: body }, { status: 400 })
    }
    return HttpResponse.json({ ok: true, message: '프로필 수정 처리가 완료되었습니다.', submitted: body })
  }),
]
