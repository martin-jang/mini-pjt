# T15 · Component Builder + 스토리

- **예상**: 60분 · **일정**: Day 10 오전 · **의존**: T08, T14
- **관련**: `SERVICE.md` §3 Component Builder, 도구 `scaffold_project`·`write_project_file`

## 목표
통일된 표준 패턴을 antd를 감싼 공통 컴포넌트로 만들고, 컴포넌트마다 스토리를 붙입니다.

## 작업
- [ ] `scaffold_project(name)`: 템플릿을 `output/{name}/`로 복사, `node_modules` 재사용, 기존 결과물 있으면 H4 승인 요청
- [ ] `write_project_file`: `check_write_path` 통과한 `src/` 경로만
- [ ] `src/codegen/component_builder.py`
  - 입력: `unification_decisions.json`, Happy Path에 쓰이는 패턴
  - 컴포넌트당 LLM 1회: 컴포넌트 코드 + 스토리 2개 이상(변형 유지 prop별 스토리 포함)
  - 크롤링 텍스트는 `wrap_as_data`로만 전달
  - 출력 잘림(`max_tokens`) 감지 시 파일 단위로 재생성

## 산출물
`src/codegen/component_builder.py`, `output/{name}/src/components/**`

## 완료 기준
- Happy Path에 필요한 공통 컴포넌트 전부 생성, 스토리 누락 0개
- `npm run build` 성공

## 절단 시
- 절단 1: 스토리는 1개씩만
