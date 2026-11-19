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

/** 계좌 활동 내역 목록 행 */
export type ActivityRow = { date: string; transaction: string; debit: string; credit: string }
export type ActivityData = { rows: ActivityRow[]; details: Record<string, Detail> }
export function getActivity(params: Record<string, string> = {}): Promise<ActivityData> {
  const q = new URLSearchParams(params).toString()
  return call<ActivityData>('/api/activity' + (q ? `?${q}` : ''))
}

/** 청구서 납부 제출 값 */
export type BillpayRequest = { payeeName: string; payeeAddressStreet: string; payeeAddressCity: string; payeeAddressState: string; payeeAddressZipcode: string; payeePhonenumber: string; payeeAccountnumber: string; verifyaccount: string; amount: string; fromaccountid: string }
export function getBillpayOptions(): Promise<Record<string, string[]>> {
  return call<Record<string, string[]>>('/api/billpay/options')
}
export function submitBillpay(req: BillpayRequest): Promise<SubmitResult> {
  return call<SubmitResult>('/api/billpay', { method: 'POST', body: JSON.stringify(req) })
}

/** 거래 내역 검색 목록 행 */
export type FindtransRow = { date: string; transaction: string; debit: string; credit: string }
export type FindtransData = { rows: FindtransRow[]; details: Record<string, Detail> }
export function getFindtrans(params: Record<string, string> = {}): Promise<FindtransData> {
  const q = new URLSearchParams(params).toString()
  return call<FindtransData>('/api/findtrans' + (q ? `?${q}` : ''))
}

/** 로그인 정보 찾기 제출 값 */
export type LookupRequest = { username: string; password: string; firstname: string; lastname: string; addressStreet: string; addressCity: string; addressState: string; addressZipcode: string; ssn: string }
export function getLookupOptions(): Promise<Record<string, string[]>> {
  return call<Record<string, string[]>>('/api/lookup/options')
}
export function submitLookup(req: LookupRequest): Promise<SubmitResult> {
  return call<SubmitResult>('/api/lookup', { method: 'POST', body: JSON.stringify(req) })
}

/** 계좌 개설 제출 값 */
export type OpenaccountRequest = { type: string; fromaccountid: string }
export function getOpenaccountOptions(): Promise<Record<string, string[]>> {
  return call<Record<string, string[]>>('/api/openaccount/options')
}
export function submitOpenaccount(req: OpenaccountRequest): Promise<SubmitResult> {
  return call<SubmitResult>('/api/openaccount', { method: 'POST', body: JSON.stringify(req) })
}

/** 계좌 개요 목록 행 */
export type OverviewRow = { account: string; balance: string; availableAmount: string }
export type OverviewData = { rows: OverviewRow[]; details: Record<string, Detail> }
export function getOverview(params: Record<string, string> = {}): Promise<OverviewData> {
  const q = new URLSearchParams(params).toString()
  return call<OverviewData>('/api/overview' + (q ? `?${q}` : ''))
}

/** 회원 가입 제출 값 */
export type RegisterRequest = { username: string; password: string; customerFirstname: string; customerLastname: string; customerAddressStreet: string; customerAddressCity: string; customerAddressState: string; customerAddressZipcode: string; customerPhonenumber: string; customerSsn: string; customerUsername: string; customerPassword: string; repeatedpassword: string }
export function getRegisterOptions(): Promise<Record<string, string[]>> {
  return call<Record<string, string[]>>('/api/register/options')
}
export function submitRegister(req: RegisterRequest): Promise<SubmitResult> {
  return call<SubmitResult>('/api/register', { method: 'POST', body: JSON.stringify(req) })
}

/** 대출 신청 제출 값 */
export type RequestloanRequest = { amount: string; downpayment: string; fromaccountid: string }
export function getRequestloanOptions(): Promise<Record<string, string[]>> {
  return call<Record<string, string[]>>('/api/requestloan/options')
}
export function submitRequestloan(req: RequestloanRequest): Promise<SubmitResult> {
  return call<SubmitResult>('/api/requestloan', { method: 'POST', body: JSON.stringify(req) })
}

/** 거래 상세 목록 행 */
export type TransactionRow = { [key: string]: string }
export type TransactionData = { rows: TransactionRow[]; details: Record<string, Detail> }
export function getTransaction(params: Record<string, string> = {}): Promise<TransactionData> {
  const q = new URLSearchParams(params).toString()
  return call<TransactionData>('/api/transaction' + (q ? `?${q}` : ''))
}

/** 자금 이체 제출 값 */
export type TransferRequest = { input: string; fromaccountid: string; toaccountid: string }
export function getTransferOptions(): Promise<Record<string, string[]>> {
  return call<Record<string, string[]>>('/api/transfer/options')
}
export function submitTransfer(req: TransferRequest): Promise<SubmitResult> {
  return call<SubmitResult>('/api/transfer', { method: 'POST', body: JSON.stringify(req) })
}

/** 프로필 수정 제출 값 */
export type UpdateprofileRequest = { customerFirstname: string; customerLastname: string; customerAddressStreet: string; customerAddressCity: string; customerAddressState: string; customerAddressZipcode: string; customerPhonenumber: string }
export function getUpdateprofileOptions(): Promise<Record<string, string[]>> {
  return call<Record<string, string[]>>('/api/updateprofile/options')
}
export function submitUpdateprofile(req: UpdateprofileRequest): Promise<SubmitResult> {
  return call<SubmitResult>('/api/updateprofile', { method: 'POST', body: JSON.stringify(req) })
}
