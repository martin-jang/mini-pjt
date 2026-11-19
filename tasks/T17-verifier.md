# T17 · Verifier·자가 수정·partial

- **예상**: 60분 · **일정**: Day 10 오전 · **의존**: T16
- **관련**: `SERVICE.md` "최종 실패 처리" (결정 D2·D9), 도구 `run_build`·`check_component_rules`·`run_happy_path_check`

## 목표
생성 앱을 검증하고, 실패하면 원인 에이전트에게 되돌려 최대 2회 고칩니다. 그래도 실패하면 부분 성공으로 정직하게 보고합니다.

## 작업
- [ ] `run_build`: `npm run build`, `npm run build-storybook` → 성공 여부 + 에러 요약
- [ ] `check_component_rules`: pages의 antd import, `allowed-deps.json` 밖 import, `FORBIDDEN_CODE_PATTERNS`, `data-testid` 누락, 스토리 누락, 라우트 누락
- [ ] `run_happy_path_check`: `vite preview` + MSW 활성, 빈 포트 자동 선택, Playwright가 `data-testid`로 단계 진행·결과 값 확인
- [ ] 자가 수정 루프: 에러 파일 → 해당 Builder에 되돌림, 최대 2회
- [ ] 2회 실패: 실패 화면만 "구현 실패" 플레이스홀더로 교체 후 재빌드, `status="partial"` + 실패 목록·에러 요약

## 산출물
`src/codegen/verifier.py`

## 완료 기준
- 일부러 TS 오류를 넣은 화면 → 2회 수정 실패 시 `partial` 응답, 나머지 빌드 성공
- 정상 생성물 → 흐름 검증 단계별 통과 리포트

## 절단 시
- 절단 1: `build-storybook` 생략
- 절단 2: Playwright 대신 정적 흐름 검사(라우트 존재 + testid 존재 + 단계 간 이동 코드 존재)
