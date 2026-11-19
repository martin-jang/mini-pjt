# T11 · Supervisor·의도 라우팅·HITL API

- **예상**: 60분 · **일정**: Day 9 오후 (**16시 체크포인트**) · **의존**: T10, T09
- **관련**: `SERVICE.md` §3 전체 흐름·API 계약 (결정 D6), `docs/GUARDRAILS.md` HITL H1~H4, Day 6 Supervisor, Day 7 `TraceCollector`

## 목표
`/query` 하나로 분석·질의·생성을 라우팅하고, 승인이 필요한 지점에서 멈췄다가 이어가는 그래프를 완성합니다.

## 작업
- [ ] `src/agent.py`
  - 입력 가드(`input_guard`) → 의도 라우팅(분석/질의/생성, Day 6 `route_question` 패턴)
  - 분석: 크롤링(H1 로그인 승인) → T07·T08·T09
  - 질의: T10 체인
  - 생성: H3(보류 항목 + Happy Path 확인) → 생성 파이프라인 자리(Day 10에 연결) / H2 이체 승인 / H4 덮어쓰기
  - `SqliteSaver(checkpoints.sqlite)` + `interrupt()`
- [ ] `app.py` 연결: `thread_id`·`approval`로 resume, `status`·`pending` 응답, 없는 `thread_id`는 400, 중복 승인 무시
- [ ] 오류 처리(E3): Bedrock 429 백오프 3회, 실패 시 안내
- [ ] trace: Day 7 `TraceCollector` 재사용 + `logs/trace.jsonl`, 단계별 `elapsed_ms`·토큰 수

## 산출물
`src/agent.py`, `app.py` 갱신

## 완료 기준 (16시)
- `curl`로 질의 → 근거 답변, `contexts`·`trace` 채워짐
- 분석 요청 → `needs_approval`(H1) → 승인 → 인벤토리 요약 응답
- 가드레일 질의(메타데이터 URL, 인젝션) → 차단 응답
