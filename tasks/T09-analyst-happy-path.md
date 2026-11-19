# T09 · Analyst ③ Happy Path + data-testid

- **예상**: 30분 · **일정**: Day 9 오후 · **의존**: T07
- **관련**: `SERVICE.md` "Happy Path 우선 구현 전략" (결정 D10·D11·D14), 도구 `derive_happy_paths`

## 목표
화면 전환 그래프에서 핵심 업무 흐름을 뽑고, 단계마다 생성 앱이 지켜야 할 `data-testid` 계약을 만듭니다.

## 작업
- [ ] `src/analyst/happy_path.py`
  - 입력: `screen_inventory.json`의 `links_to`, 화면 성격
  - **크롤링 근거가 있는 화면으로만** 흐름 구성 (결과 화면 근거 없으면 제외)
  - 각 단계: `step_id`, 화면 ID, 사용자 행동(클릭·입력), `data-testid`, 기대 결과
  - 흐름 0개면 생성 중단 사유 반환 (D1x)
- [ ] 결과: `data/analysis/happy_paths.json`

## 산출물
`src/analyst/happy_path.py`, `data/analysis/happy_paths.json`

## 완료 기준
- 실제 스냅샷 기준 조회 흐름 + 이체 흐름 2개 도출, 납부 흐름 미포함
- 모든 단계에 고유 `data-testid`

## 절단 시
- 절단 4: 조회 흐름만
