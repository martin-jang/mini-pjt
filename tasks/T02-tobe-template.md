# T02 · 고정 TOBE 템플릿

- **예상**: 60분 · **일정**: Day 9 오전 · **의존**: 없음 (T01과 병행 가능)
- **관련**: `SERVICE.md` §3 "생성 앱의 실행 환경" (결정 D8 고정 템플릿)

## 목표
생성 앱의 바탕이 될 템플릿을 만들고, **검증된 버전 조합으로 설치·빌드가 되는지** 먼저 확인합니다. LLM은 이후 `src/`만 씁니다.

## 작업
- [ ] `templates/tobe-app/`에 Vite + React + TypeScript 프로젝트 생성
- [ ] 의존성 추가 후 **정확한 버전으로 pin**: react-router, antd, msw, storybook(react-vite), @playwright/test
- [ ] MSW worker 파일 생성(`npx msw init public/`), `src/mocks/browser.ts` 기본 구조, **활성 플래그**(`VITE_ENABLE_MSW`)로 preview에서 켜기
- [ ] Storybook 기본 설정 + 샘플 스토리 1개
- [ ] Playwright 설정 + 샘플 테스트 1개 (`vite preview` 대상)
- [ ] `npm install` 1회 (설치 스크립트는 템플릿 작성자가 확인한 것만)
- [ ] 허용 의존성 목록을 `templates/tobe-app/allowed-deps.json`으로 저장 (Verifier가 사용)

## 산출물
`templates/tobe-app/` (package.json, lock 파일, 설정), `allowed-deps.json`

## 완료 기준
- `npm run build` 성공
- `npm run build-storybook` 성공
- `vite preview` + MSW 활성 상태에서 샘플 Playwright 테스트 통과
- 고정한 버전 목록을 이 파일 하단에 기록

## 절단 시
- 절단 1: Storybook은 설정만 두고 빌드 확인 생략
- 절단 2: Playwright 설정 생략

## 기록 (완료 후 작성)
- 상태: **완료** — `npm run build:mock`, `npm run build-storybook`, `npx playwright test`(vite preview + MSW) 모두 통과
- 고정 버전: react 19.3.1, react-dom 19.3.1, react-router 8.5.1, antd 6.7.1, msw 3.0.7, vite 8.3.8, typescript 7.0.2, storybook·@storybook/react-vite 10.6.7, @playwright/test 1.65.1
- 발견: MSW v3는 `worker.start({ onUnhandledRequest })` 옵션이 없음 → LLM이 v2 지식으로 쓰면 빌드 실패. 고정 템플릿(D8)의 필요성 확인
- 발견: npm 11은 설치 스크립트를 기본 차단 (esbuild postinstall 차단 상태로도 빌드 정상)
- `tsconfig.app.json`의 `noUnusedLocals/Parameters`는 생성 코드 안정성을 위해 false로 완화
- MSW 활성: `.env.mock`(`VITE_ENABLE_MSW=true`) + `npm run build:mock`
