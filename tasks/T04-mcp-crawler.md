# T04 · fastmcp 크롤러 서버 (읽기 전용)

- **예상**: 60분 · **일정**: Day 9 오전 · **의존**: T03
- **관련**: `SERVICE.md` §3 도구 목록, `docs/GUARDRAILS.md` G1·G2·G3, Day 4 MCP 패턴

## 목표
Playwright로 화면을 읽기 전용으로 수집하는 MCP 서버를 만듭니다. 가드레일은 이 서버의 **도구 경계에서** 강제합니다 (README 핵심 의사결정 #2 근거).

## 작업
- [ ] `playwright install chromium`
- [ ] `mcp_server/crawler_server.py` (fastmcp)
  - `crawl_site(url, max_depth, max_pages)`: 같은 허용 도메인 링크만 BFS, 각 URL은 `check_url` 통과 필수, 리다이렉트 대상도 재검사
  - `capture_page(url)`: DOM 요약(폼 필드·버튼·테이블 헤더·링크·제목), 스크린샷 경로
  - `login_with_demo_account()`: 계정은 `.env`에서, **HITL 승인 후에만 호출**된다는 전제를 docstring에 명시
  - 폼 제출·상태 변경 클릭은 하지 않음 (G2)
- [ ] 수집 결과는 `mask_pii` 적용 후 `data/snapshots/{도메인}/`에 JSON 저장
- [ ] **스냅샷 재생 모드**: `snapshot_mode=replay`이면 네트워크 대신 저장된 JSON 반환

## 산출물
`mcp_server/crawler_server.py`, `data/snapshots/` 저장 형식

## 완료 기준
- 서버 단독 기동 후 허용 도메인 시작 URL로 `crawl_site` 실행 → 화면 JSON 저장
- `169.254.169.254` 요청 → 거부 안내 문자열
- 재생 모드에서 네트워크 없이 같은 결과 반환

## 절단 시
- 절단 3: fastmcp 서버 대신 같은 함수를 LangChain `@tool`로 직접 노출 (가드레일 코드는 그대로)
