# T14 · API 계약·MSW 결정적 생성

- **예상**: 45분 · **일정**: Day 10 오전 · **의존**: T02, T09
- **관련**: `SERVICE.md` "데이터: MSW + 고정 API 계약" (결정 D7·D13)

## 목표
생성 앱의 API 타입·엔드포인트·MSW 핸들러·더미 데이터를 **LLM 없이 코드로** 만듭니다. 화면과 mock이 어긋나는 실패를 원천 차단합니다.

## 작업
- [ ] `src/codegen/contracts.py`
  - 입력: `screen_inventory.json`, `happy_paths.json`
  - 출력: `src/api/types.ts`(화면별 데이터 타입), `src/api/client.ts`(엔드포인트 함수)
- [ ] `src/codegen/mocks.py`
  - 출력: `src/mocks/handlers.ts`(로그인·조회·이체 동작, 메모리 잔액 갱신), `src/mocks/data.ts`(스냅샷에서 뽑아 **마스킹한** 더미 값)
- [ ] 템플릿 복사본에 쓰고 `npm run build`로 타입 확인

## 산출물
`src/codegen/contracts.py`, `src/codegen/mocks.py`

## 완료 기준
- 생성된 계약·핸들러만 넣은 템플릿이 빌드 성공
- 더미 데이터에 마스킹 안 된 값 없음
- 사이트 고유 값 하드코딩 없음 (입력 JSON에서만)
