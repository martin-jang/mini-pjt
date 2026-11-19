# T10 · RAG 적재·검색·근거 없음

- **예상**: 45분 · **일정**: Day 9 오후 · **의존**: T07, T08
- **관련**: `SERVICE.md` "질의응답(RAG) 근거 구성" (결정 D18), Day 2 `build_retriever`·`assess_retrieval`

## 목표
채점 중심인 L1 질의응답 경로입니다. 화면·통일 결정 단위 문서로 적재하고, 근거가 부족하면 모델을 부르지 않습니다.

## 작업
- [ ] `src/retriever.py`
  - 문서 생성: 화면 1개 = 문서 1개(필드·버튼·테이블·전환 요약 + `screen_id`·`url` 메타), 통일 결정 1건 = 문서 1개, Happy Path 1개 = 문서 1개
  - Chroma(`./chroma_db`, Titan v2) 적재, Day 2 하이브리드(BM25 + 벡터) 검색 재사용
  - `retrieve_screens(query, k)` 도구
- [ ] 답변 체인: 검색 → `assess_retrieval` → 부족하면 "근거 없음" / 충분하면 근거 기반 답변
- [ ] `contexts`에 검색 문서(`doc_id`, `text`)를 그대로 담기

## 산출물
`src/retriever.py`, 답변 체인

## 완료 기준
- `test_queries.json` 2·20번류 질의 → 근거 URL 포함 답변
- 6·7번류(없는 화면) → "근거 없음", 모델 미호출
- 가짜 LLM·가짜 임베딩 단위 테스트 통과
