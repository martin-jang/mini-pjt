# T08 · Analyst ② 변이 클러스터링·통일 결정

- **예상**: 60분 · **일정**: Day 9 오후 · **의존**: T06, T07
- **관련**: `SERVICE.md` "UI 변이 정규화(통일) 전략", 도구 `cluster_ui_variants`·`decide_unification`

## 목표
이 서비스의 핵심 차별점입니다. 화면 간 같은 역할의 UI 요소를 묶고, 표준을 추론해 **통일 / 변형 유지 / 보류**로 분류합니다.

## 작업
- [ ] `src/analyst/variants.py` `cluster_ui_variants`: 요소 단위 수집 → 라벨 임베딩 유사도(Titan) + 맥락 + 구조로 그룹화
- [ ] `src/analyst/unification.py` `decide_unification`
  - 표준 추론 순서: ① 다수결(Happy Path 가중치) ② UX 관례·antd 기본 ③ 일관성
  - **동작이 바뀌는 통일은 자동 금지** → 변형 유지 또는 보류 (과잉 통일 방지)
  - 결과: `unification_decisions.json` (ASIS 변이 → TOBE 표준 → 결정 → 근거 → 확신도)
- [ ] 보류 항목은 H3 HITL에서 사용자에게 보여줄 형태로 정리

## 산출물
`src/analyst/variants.py`, `src/analyst/unification.py`, `data/analysis/unification_decisions.json`

## 완료 기준
- 픽스처 대상 실행 → 변이 그룹 recall ≥ 80%, 과잉 통일 0건 (`evaluation/golden/` 비교)
- 모든 결정에 근거 기재
- 가짜 LLM 단위 테스트 통과

## 줄일 수 있는 부분
- 레이아웃 변이는 규칙 기반 비교만, LLM 판단은 라벨·형식 변이에만
