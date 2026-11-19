# T07 · Analyst ① 화면 인벤토리

- **예상**: 45분 · **일정**: Day 9 오후 · **의존**: T05
- **관련**: `SERVICE.md` §3 Analyst, 도구 `build_screen_inventory`, Day 1 Pydantic 구조화 출력

## 목표
스냅샷을 화면·필드·액션·화면 전환 구조로 정리한 `screen_inventory.json`을 만듭니다. 이후 모든 분석과 RAG의 기반입니다.

## 작업
- [ ] `src/analyst/inventory.py`
  - Pydantic 스키마: `Screen(id, url_pattern, title, kind[조회/입력/결과], requires_login, fields[], buttons[], tables[], links_to[])`
  - **URL 패턴 정규화**: 쿼리스트링 값(계좌번호 등)만 다른 URL은 같은 화면으로 묶기
  - 구조 정보(폼·테이블·링크)는 규칙으로 추출, 화면 성격 분류만 LLM 사용
  - LLM 출력 검증 실패 시 오류를 붙여 1회 재요청 (E3)
- [ ] 사이트 고유 값 하드코딩 금지 (화면명·필드명은 데이터에서만)

## 산출물
`src/analyst/inventory.py`, `data/analysis/screen_inventory.json`

## 완료 기준
- 가짜 LLM 단위 테스트 통과 (배선 검증)
- 실제 스냅샷 대상 실행 → 화면 recall을 `evaluation/golden/screens.json`과 비교해 출력
- 상세 화면이 계좌별로 중복 집계되지 않음
