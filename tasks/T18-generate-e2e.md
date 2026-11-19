# T18 · 생성 E2E + 백업 결과물

- **예상**: 30분 · **일정**: Day 10 오전 · **의존**: T17
- **관련**: `SERVICE.md` 데이터 소스 "생성 POC 백업", 운영 지표(URL → POC 소요 시간)

## 목표
`/query` 한 흐름으로 URL 입력부터 POC 생성·검증까지 처음부터 끝까지 돌리고, 시연용 백업 결과물을 남깁니다.

## 작업
- [ ] `src/agent.py` 생성 경로에 T14~T17 연결
- [ ] 스냅샷 재생 모드로 "분석 → 승인 → 생성 → 승인 → 검증" 전체 실행
- [ ] trace의 단계별 `elapsed_ms`로 총 소요 시간 기록
- [ ] 결과물을 `output/parabank-next/`로 확정 (node_modules 제외 커밋 대상)

## 산출물
`output/parabank-next/`, 소요 시간 기록

## 완료 기준
- `status="ok"` 또는 근거 있는 `partial`
- `npm run dev`로 띄워 Happy Path를 사람이 직접 클릭해 확인
