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
  http.get('/api/mainpage', () => HttpResponse.json(listData['mainpage'])),
  http.get('/api/addbbsmaster/options', () => HttpResponse.json(optionData['addbbsmaster'] ?? {})),
  http.post('/api/addbbsmaster', async ({ request }) => {
    const body = (await request.json()) as Record<string, string>
    const empty = Object.entries(body).filter(([, v]) => !String(v ?? '').trim()).map(([k]) => k)
    if (empty.length) {
      return HttpResponse.json({ ok: false, message: `입력이 필요합니다: ${empty.join(', ')}`, submitted: body }, { status: 400 })
    }
    return HttpResponse.json({ ok: true, message: '게시판 템플릿 등록 처리가 완료되었습니다.', submitted: body })
  }),
  http.get('/api/bbsAddboardarticle/options', () => HttpResponse.json(optionData['bbsAddboardarticle'] ?? {})),
  http.post('/api/bbsAddboardarticle', async ({ request }) => {
    const body = (await request.json()) as Record<string, string>
    const empty = Object.entries(body).filter(([, v]) => !String(v ?? '').trim()).map(([k]) => k)
    if (empty.length) {
      return HttpResponse.json({ ok: false, message: `입력이 필요합니다: ${empty.join(', ')}`, submitted: body }, { status: 400 })
    }
    return HttpResponse.json({ ok: true, message: '공지사항 글 등록 처리가 완료되었습니다.', submitted: body })
  }),
  http.get('/api/adminAddboardarticle/options', () => HttpResponse.json(optionData['adminAddboardarticle'] ?? {})),
  http.post('/api/adminAddboardarticle', async ({ request }) => {
    const body = (await request.json()) as Record<string, string>
    const empty = Object.entries(body).filter(([, v]) => !String(v ?? '').trim()).map(([k]) => k)
    if (empty.length) {
      return HttpResponse.json({ ok: false, message: `입력이 필요합니다: ${empty.join(', ')}`, submitted: body }, { status: 400 })
    }
    return HttpResponse.json({ ok: true, message: '공지사항 글 등록(관리자) 처리가 완료되었습니다.', submitted: body })
  }),
  http.get('/api/adminSelectboardlist', () => HttpResponse.json(listData['adminSelectboardlist'])),
  http.get('/api/selectbbsmasterinf', () => HttpResponse.json(listData['selectbbsmasterinf'])),
  http.get('/api/selectbbsmasterinfs', () => HttpResponse.json(listData['selectbbsmasterinfs'])),
  http.get('/api/bbsSelectboardlist', () => HttpResponse.json(listData['bbsSelectboardlist'])),
  http.get('/api/addbbsuseinf/options', () => HttpResponse.json(optionData['addbbsuseinf'] ?? {})),
  http.post('/api/addbbsuseinf', async ({ request }) => {
    const body = (await request.json()) as Record<string, string>
    const empty = Object.entries(body).filter(([, v]) => !String(v ?? '').trim()).map(([k]) => k)
    if (empty.length) {
      return HttpResponse.json({ ok: false, message: `입력이 필요합니다: ${empty.join(', ')}`, submitted: body }, { status: 400 })
    }
    return HttpResponse.json({ ok: true, message: '게시판 사용 등록 처리가 완료되었습니다.', submitted: body })
  }),
  http.get('/api/selectbbsuseinf', () => HttpResponse.json(listData['selectbbsuseinf'])),
  http.get('/api/selectbbsuseinfs', () => HttpResponse.json(listData['selectbbsuseinfs'])),
]
