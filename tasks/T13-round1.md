# T13 · round1 실행·리포트

- **예상**: 30분 · **일정**: Day 9 저녁 (**18시 체크포인트**) · **의존**: T12
- **관련**: `ASSIGNMENT.md` Day 9 "round1_report.md", `SERVICE.md` §5

## 목표
1차 자체 평가 결과를 리포트로 남깁니다. 생성 경로가 아직 없어도 **있는 그대로** 기록합니다.

## 작업
- [ ] `python evaluation/run_eval.py --round 1`
- [ ] `evaluation/round1_report.md`
  - 케이스별 통과/실패와 실패 원인
  - RAGAS 4종, L2(화면·필드·변이 recall, 과잉 통일), L4 결과
  - 미구현 범위(생성 케이스 5·14번 등) 명시
  - 목표치 대비 차이, 2차까지 개선할 항목 Top 3
  - 목표치를 조정한다면 근거 (`SERVICE.md` §5 각주)
- [ ] 커밋 (사용자 요청 시)

## 산출물
`evaluation/round1_report.md`

## 완료 기준
- 18시까지 리포트 파일 존재, 수치는 실제 실행 결과에서 옴
