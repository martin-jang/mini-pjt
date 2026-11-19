# T12 · 평가 하네스 + RAGAS

- **예상**: 60분 · **일정**: Day 9 오후 · **의존**: T11
- **관련**: `SERVICE.md` §5 지표·평가 운영 원칙 (결정 D15), `evaluation/README.md`, Day 7 `run_eval`·`compare_eval`

## 목표
`test_queries.json`을 `/query`에 돌려 L1~L4 지표를 한 번에 산출하는 하네스를 만듭니다.

## 작업
- [ ] **결정 필요**: RAGAS `reference`(정답 답변)를 제출 CSV 컬럼으로도 넣을지, 하네스 내부 파일(`evaluation/golden/references.json`)로만 둘지 → 사용자 확인
- [ ] 질의 케이스(2·3·4·6·7·9·15~20)의 `reference` 작성 (스냅샷 기준)
- [ ] `evaluation/run_eval.py`
  - 스냅샷 재생 모드 고정, 케이스별 `auto_approve` 처리 (`false`면 `needs_approval` 자체를 정답으로)
  - `expected_traits`·`forbidden`: LLM-as-Judge (Day 6 `judge_output` 패턴)
  - `expected_tools`: trace에서 호출 도구 비교
  - RAGAS 4종: **L1 질의 케이스만**
  - L2: `evaluation/golden/`과 결정적 비교
  - L4: 차단·승인 요청 결정적 검사
  - 결과 JSON 저장 + 요약 출력
- [ ] Day 7 `compare_eval`로 라운드 간 비교 함수 준비

## 산출물
`evaluation/run_eval.py`, `evaluation/golden/references.json`, `evaluation/results/round1.json`

## 완료 기준
- 20건 전체 실행 완료(실패 케이스도 결과에 기록)
- 통과율·RAGAS 4종·L2·L4 지표가 한 화면에 출력

## 줄일 수 있는 부분
- Judge 호출을 케이스당 1회로 묶기
