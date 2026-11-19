// 생성 시 Analyst 산출물로 결정적으로 덮어쓰는 API 계약 파일입니다 (LLM 작성 금지).
export interface SampleResponse {
  message: string
}

export async function getSample(): Promise<SampleResponse> {
  const res = await fetch('/api/sample')
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
