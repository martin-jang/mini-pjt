# T16 · Page Builder + 라우트·플레이스홀더

- **예상**: 45분 · **일정**: Day 10 오전 · **의존**: T15
- **관련**: `SERVICE.md` §3 Page Builder (결정 D3·D14)

## 목표
공통 컴포넌트만 써서 Happy Path 화면을 구현하고, 나머지 화면은 라우트와 "구현 예정" 페이지로 전체 구조를 보여줍니다.

## 작업
- [ ] `src/codegen/page_builder.py`
  - Happy Path 화면: LLM이 `src/components`와 `src/api/client.ts`만 import해 작성, 단계별 `data-testid` 필수
  - 나머지 화면: 템플릿 코드로 "구현 예정" 플레이스홀더 생성 (LLM 미사용)
  - `routes.tsx`: 인벤토리 전 화면 라우트 + 메뉴
- [ ] 화면 라벨은 `unification_decisions.json`의 표준을 따름

## 산출물
`src/codegen/page_builder.py`, `output/{name}/src/pages/**`, `routes.tsx`

## 완료 기준
- 라우트 커버리지 ≥ 90% (플레이스홀더 포함)
- Happy Path 화면에 모든 `data-testid` 존재
- pages에서 antd 직접 import 0건
