# T03 · 가드레일 공통 모듈

- **예상**: 45분 · **일정**: Day 9 오전 · **의존**: T01
- **관련**: `docs/GUARDRAILS.md` G1~G5, Day 5 `input_guard`·`mask_pii`·`needs_approval`

## 목표
크롤러·생성 코드가 공통으로 쓰는 가드레일 검사를 한 모듈에 모읍니다. 가드레일은 프롬프트가 아니라 이 함수들로 강제합니다.

## 작업
- [ ] `src/guardrails.py`
  - `check_url(url)`: 허용 도메인 + DNS 해석 후 IP 검사(사설·루프백·링크 로컬 `169.254/16`·`file://` 거부) → `(허용 여부, 이유)` (G1)
  - `input_guard(text)`: Day 5 재사용, 직접 인젝션 차단 (G4)
  - `mask_pii(text)`: Day 5 재사용 + 계좌번호·SSN 패턴 보강 (G3)
  - `wrap_as_data(text)`: 크롤링 텍스트를 구분자 데이터 블록으로 감싸기 (G4)
  - `FORBIDDEN_CODE_PATTERNS`: `dangerouslySetInnerHTML`, 하드코딩 외부 URL, `eval`, `new Function` (G4)
  - `check_write_path(path, project_root)`: `src/` 밖·`..`·템플릿 파일 거부 (G5)
- [ ] `tests/test_guardrails.py`: 각 함수의 허용·거부 케이스

## 산출물
`src/guardrails.py`, `tests/test_guardrails.py`

## 완료 기준
- `pytest tests/test_guardrails.py` 통과
- 최소 포함: `169.254.169.254` 거부, 허용 도메인 통과, `../package.json` 쓰기 거부, SSN 마스킹

## 주의
- 거부 시 예외 대신 **안내 문자열**을 돌려줄 수 있게 이유를 함께 반환합니다.
