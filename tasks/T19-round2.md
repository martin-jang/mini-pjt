# T19 · round2 + 개선폭 비교

- **예상**: 30분 · **일정**: Day 10 오후 · **의존**: T18
- **관련**: `ASSIGNMENT.md` Day 10 "round2_report.md (개선폭 명시)", Day 7 `compare_eval`

## 목표
2차 평가를 돌리고 1차 대비 개선폭을 리포트로 남깁니다. 채점 항목 "1차 → 2차 개선폭"의 근거입니다.

## 작업
- [ ] `python evaluation/run_eval.py --round 2`
- [ ] `compare_eval(round1, round2)`로 개선·회귀 케이스 목록
- [ ] `evaluation/round2_report.md`
  - 통과율 1차 → 2차, 개선폭 +N건
  - 주요 개선 사항과 각각의 원인 변경
  - 회귀 케이스와 이유
  - 남은 실패와 한계
- [ ] `python evaluation/json_to_csv.py`로 제출 CSV 최신화

## 산출물
`evaluation/round2_report.md`, `evaluation/results/round2.json`

## 완료 기준
- 수치가 실제 실행 결과에서 옴, 회귀가 있으면 숨기지 않고 기록
