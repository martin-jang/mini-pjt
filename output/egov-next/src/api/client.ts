// 교육용 더미 데이터입니다. 이 파일은 Legacy2Next가 결정적으로 생성합니다 (LLM 작성 금지).

export type SubmitResult = { ok: boolean; message: string; submitted: Record<string, string> }
export type Detail = { label: string; value: string }
export type LoginRequest = { username: string; password: string }
export type LoginResult = { ok: boolean; message: string; user?: string }

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...init })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body.message ?? `HTTP ${res.status}`)
  return body as T
}

export function login(req: LoginRequest): Promise<LoginResult> {
  return call<LoginResult>('/api/auth/login', { method: 'POST', body: JSON.stringify(req) })
}

/** 메인 홈(대시보드) 목록 행 */
export type MainpageRow = { f5New: string; col2: string; f20261119: string }
export type MainpageData = { rows: MainpageRow[]; details: Record<string, Detail> }
export function getMainpage(params: Record<string, string> = {}): Promise<MainpageData> {
  const q = new URLSearchParams(params).toString()
  return call<MainpageData>('/api/mainpage' + (q ? `?${q}` : ''))
}

/** 게시판 템플릿 등록 제출 값 */
export type AddbbsmasterRequest = { bbsnm: string; bbsintrcn: string; bbstycode: string; bbsattrbcode: string; replyposblat: string; fileatchposblat: string; posblatchfilenumber: string; tmplatnm: string }
export function getAddbbsmasterOptions(): Promise<Record<string, string[]>> {
  return call<Record<string, string[]>>('/api/addbbsmaster/options')
}
export function submitAddbbsmaster(req: AddbbsmasterRequest): Promise<SubmitResult> {
  return call<SubmitResult>('/api/addbbsmaster', { method: 'POST', body: JSON.stringify(req) })
}

/** 공지사항 글 등록 제출 값 */
export type BbsAddboardarticleRequest = { nttsj: string; nttcn: string; file0: string }
export function getBbsAddboardarticleOptions(): Promise<Record<string, string[]>> {
  return call<Record<string, string[]>>('/api/bbsAddboardarticle/options')
}
export function submitBbsAddboardarticle(req: BbsAddboardarticleRequest): Promise<SubmitResult> {
  return call<SubmitResult>('/api/bbsAddboardarticle', { method: 'POST', body: JSON.stringify(req) })
}

/** 공지사항 글 등록(관리자) 제출 값 */
export type AdminAddboardarticleRequest = { nttsj: string; nttcn: string; file0: string }
export function getAdminAddboardarticleOptions(): Promise<Record<string, string[]>> {
  return call<Record<string, string[]>>('/api/adminAddboardarticle/options')
}
export function submitAdminAddboardarticle(req: AdminAddboardarticleRequest): Promise<SubmitResult> {
  return call<SubmitResult>('/api/adminAddboardarticle', { method: 'POST', body: JSON.stringify(req) })
}

/** 공지사항 목록(관리자) 목록 행 */
export type AdminSelectboardlistRow = { col1: string; col2: string; col3: string; col4: string; col5: string }
export type AdminSelectboardlistData = { rows: AdminSelectboardlistRow[]; details: Record<string, Detail> }
export function getAdminSelectboardlist(params: Record<string, string> = {}): Promise<AdminSelectboardlistData> {
  const q = new URLSearchParams(params).toString()
  return call<AdminSelectboardlistData>('/api/adminSelectboardlist' + (q ? `?${q}` : ''))
}

/** 게시판 생성 상세 목록 행 */
export type SelectbbsmasterinfRow = { [key: string]: string }
export type SelectbbsmasterinfData = { rows: SelectbbsmasterinfRow[]; details: Record<string, Detail> }
export function getSelectbbsmasterinf(params: Record<string, string> = {}): Promise<SelectbbsmasterinfData> {
  const q = new URLSearchParams(params).toString()
  return call<SelectbbsmasterinfData>('/api/selectbbsmasterinf' + (q ? `?${q}` : ''))
}

/** 게시판 생성 목록 목록 행 */
export type SelectbbsmasterinfsRow = { col1: string; col2: string; col3: string; col4: string; col5: string; col6: string }
export type SelectbbsmasterinfsData = { rows: SelectbbsmasterinfsRow[]; details: Record<string, Detail> }
export function getSelectbbsmasterinfs(params: Record<string, string> = {}): Promise<SelectbbsmasterinfsData> {
  const q = new URLSearchParams(params).toString()
  return call<SelectbbsmasterinfsData>('/api/selectbbsmasterinfs' + (q ? `?${q}` : ''))
}

/** 공지사항 목록 목록 행 */
export type BbsSelectboardlistRow = { col1: string; col2: string; col3: string; col4: string; col5: string }
export type BbsSelectboardlistData = { rows: BbsSelectboardlistRow[]; details: Record<string, Detail> }
export function getBbsSelectboardlist(params: Record<string, string> = {}): Promise<BbsSelectboardlistData> {
  const q = new URLSearchParams(params).toString()
  return call<BbsSelectboardlistData>('/api/bbsSelectboardlist' + (q ? `?${q}` : ''))
}

/** 게시판 사용 등록 제출 값 */
export type AddbbsuseinfRequest = { bbsnm: string; trgettype: string; trgetnm: string }
export function getAddbbsuseinfOptions(): Promise<Record<string, string[]>> {
  return call<Record<string, string[]>>('/api/addbbsuseinf/options')
}
export function submitAddbbsuseinf(req: AddbbsuseinfRequest): Promise<SubmitResult> {
  return call<SubmitResult>('/api/addbbsuseinf', { method: 'POST', body: JSON.stringify(req) })
}

/** 게시판 사용 상세 목록 행 */
export type SelectbbsuseinfRow = { col1: string; col2: string }
export type SelectbbsuseinfData = { rows: SelectbbsuseinfRow[]; details: Record<string, Detail> }
export function getSelectbbsuseinf(params: Record<string, string> = {}): Promise<SelectbbsuseinfData> {
  const q = new URLSearchParams(params).toString()
  return call<SelectbbsuseinfData>('/api/selectbbsuseinf' + (q ? `?${q}` : ''))
}

/** 게시판 사용 목록 목록 행 */
export type SelectbbsuseinfsRow = { col1: string; col2: string; col3: string; col4: string; col5: string; col6: string }
export type SelectbbsuseinfsData = { rows: SelectbbsuseinfsRow[]; details: Record<string, Detail> }
export function getSelectbbsuseinfs(params: Record<string, string> = {}): Promise<SelectbbsuseinfsData> {
  const q = new URLSearchParams(params).toString()
  return call<SelectbbsuseinfsData>('/api/selectbbsuseinfs' + (q ? `?${q}` : ''))
}
