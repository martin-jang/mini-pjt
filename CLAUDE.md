# CLAUDE.md — Mini PJT 작업 지침

## 프로젝트 개요

- **주제**: Legacy2Next — URL 하나로 레거시 웹 시스템을 분석해 차세대 React 프론트엔드 POC를 1일 안에 생성하는 에이전트
- **대상 업무 / 반복 작업**: 레거시 현대화 과제 착수 시 화면 분석 → 공통 컴포넌트 설계 → 목업/POC 제작 (현재 1~2주 수작업)

## 기술 스택 / 환경

- **런타임**: Python 3.14 (`agent/.venv`), Node v26
- **에이전트**: LangGraph 고정 그래프 (Router + 단계별 노드, `interrupt()`로 사용자 승인), 체크포인트 SqliteSaver
- **LLM / 임베딩**: AWS Bedrock Claude Sonnet 4.6 (추론 프로필 `global.anthropic.claude-sonnet-4-6`, Anthropic SDK `AsyncAnthropicBedrock` = bedrock-runtime) / Titan Embeddings v2. 현재 계정은 Sonnet 5.x 접근 권한과 bedrock-mantle IAM 권한이 없다. 권한이 생기면 `.env`의 `BEDROCK_MODEL_ID`만 바꾼다
- **RAG**: Chroma
- **화면 수집**: Playwright MCP (`microsoft/playwright-mcp`)
- **개인정보 마스킹**: Presidio (`presidio-analyzer`, `presidio-anonymizer`, `presidio-image-redactor` + Tesseract OCR `kor`)
- **UI 디자인**: Stitch MCP로 화면 디자인 생성
- **생성물(TOBE)**: React + Vite + TypeScript + React Router + Tailwind CSS, Storybook, Playwright 검증
- **API 서버**: FastAPI (`/query` 단일 진입점)
- **비밀값**: `.env`에서만 읽음 (`.env.example` 제공)

## 디렉터리 구조

루트는 역할별로 세 폴더로 나눈다.

### `agent/` — 에이전트 구동 코드
- `.venv/` — Python 가상환경 (git 제외)
- `config/settings.yaml` — 한도 값(G8), 콘솔 CORS, 로그 위치, 사이트별 추가 허용 origin(G2). 비밀값은 넣지 않는다
- `legacy2next/` — 에이전트 패키지
  - `config.py` — 설정·`.env` 로더, origin 계산, 사이트 계정(`SITE_<별칭>_USERNAME/PASSWORD`)
  - `masking.py` — 비밀값 마스킹 레지스트리와 로그 필터 (G3)
  - `events.py` — 실행 이벤트 로그 (`logs/runs/<실행 ID>.jsonl`, SSE 구독)
  - `llm.py` — LLM 게이트웨이(Anthropic SDK Bedrock): 호출 수 한도(G8), 입력 마스킹, 호출 기록, 거절 처리. 노드는 이것으로만 LLM을 부른다
  - `schemas.py` — 콘솔과 주고받는 데이터 구조 (`ui/src/api/types.ts`와 같은 모양, camelCase JSON)
  - `graph.py` — LangGraph 고정 그래프: Router → ①~⑤ 노드, 승인 게이트 2곳(`interrupt()`), 상태 알림용 게이트 노드
  - `runs.py` — 실행 시작·재개·중단, 이벤트 로그를 접어 콘솔용 실행 스냅샷을 만든다 (실행 ID = 별칭 = 그래프 thread_id)
  - `stubs.py` — 실제 노드가 붙기 전 스텁 데이터. 노드가 구현되면 줄여 나간다
  - `router.py` — Router: 자유 문장 의도 분류(신규 생성·확장·질의·범위 밖), LLM 출력 재검사, 범위 밖 거절(G4, `logs/router/`에 기록). 새 요청 폼은 LLM을 부르지 않는다
  - `fake_llm.py` — 테스트용 가짜 LLM 클라이언트(`--fake-llm`)
  - `browser.py` — Playwright MCP 연결(`McpBrowser`)과 가드 래퍼(`GuardedBrowser`): 허용 도구 목록(G1), 이동 전·후 origin 검사와 되돌림(G2). Explorer는 이 래퍼로만 브라우저를 다룬다
  - `explorer.py` — Map(T07c): 너비 우선으로 화면을 돌며 `crawl/graph.json`(화면 노드·이동 엣지·메뉴 트리) 생성. 조회만, LLM 호출 없음. 주소 링크는 따라가고, 스크립트 메뉴는 메뉴 영역(nav·header·aside)에서만 클릭, 위험 이름·파일·본문 스크립트 링크는 이유와 함께 건너뜀. 상한 `explorer.max_screens·max_depth·max_per_pattern`. 로그인 화면으로 되돌아가면 세션 만료. 흐름 걷기는 T07d
  - `login.py` — 로그인 유형 판별(LLM은 입력란 ref만 고름), ID/PW 값은 코드가 `--secrets` 키 이름으로 입력(G3), 그 외 인증은 사용자에게 넘김(인증 브라우저 `AuthHandoffs`), 세션 저장·마스킹 등록(G10)
  - `walker.py` — Hypothesize·Walk(T07d): 사이트맵 요약으로 LLM이 사이트 성격 1차 추론과 유스케이스 후보 5~7개(점수)를 내고(`crawl/hypotheses.json`), 점수 높은 후보부터 LLM이 화면을 보며 동작을 하나씩 고르면 코드가 검사 후 실행(쓰기 동작은 T08 전까지 실행하지 않고 멈춤, 계정 값 입력 거부). 완주 목표(기본 3)에 닿으면 멈추고, 흐름마다 Flow Trace(`crawl/flows/<id>.json`)와 역할+이름 기준 재실행 스크립트를 남겨 LLM 없이 다시 걸어 재현을 확인한다
  - `crawl.py` — 수집 데이터 구조(`next-pjt/<별칭>/crawl/`): 원본·파생·manifest Pydantic 모델(schema_version), 저장소(`CrawlStore`, crawl 폴더 밖 쓰기 금지), 파생 다시 만들기 CLI
  - `capture.py` — 화면 하나의 원본 수집(스크린샷·접근성 스냅샷·줄인 DOM·네트워크·콘솔). 저장 전 마스킹
  - `derive.py` — 원본 `dom.min.html`만으로 `layout.json`·`components.json`·`tokens.json`을 만든다 (브라우저·LLM 없음)
  - `scripts/` — 고정 읽기 전용 추출 스크립트(G1 예외). `GuardedBrowser.run_fixed_script(이름)`으로만 실행한다. `capture_dom.js`는 요소마다 위치(`data-l2n-box`)·적용 스타일(`data-l2n-style`)을 붙이고 입력값은 남기지 않는다
  - `api.py`, `__main__.py` — FastAPI 앱(`/query`, `/runs`, 승인·인증 완료·세션 삭제·중단, SSE)과 서버 실행
- `tests/` — pytest (실제 Bedrock 호출 없이 가짜 모델로 검증). `tests/fixtures/site_server.py`: 시험 사이트 — `/`(외부 링크·외부 리다이렉트, G2), `/board.html`(머리글·왼쪽 메뉴·검색 폼·표·탭·페이징이 있는 목록 화면, T07b. 제목 → `/board/view.html?id=N` 상세, 검색어로 제목 거르기, T07d 흐름 걷기용), `/idpw/`(ID/PW 로그인, 계정 `tester`/`fixture-pass-1234`), `/cert/`(간편인증, `POST /_test/approve`로 승인 흉내), `POST /_test/expire`(세션 만료 흉내)
- `mcp/` — 에이전트가 띄우는 MCP 서버 npm 패키지 (버전 고정, `node_modules`는 git 제외)

### `next-pjt/<별칭>/` — 사이트별 생성 결과물 (git 제외)
- 요청한 웹 사이트마다 별칭 폴더 하나 (예: `next-pjt/parabank/`)
- `design/` — Stitch로 만든 TOBE 화면 디자인 (HTML·스크린샷)
- 그 외 — 생성된 React POC 프로젝트

### `ui/` — 시스템 콘솔 UI
- 에이전트에 요청을 보내고 진행 상황과 결과를 확인하는 화면
- 스택: React + Vite + TypeScript + Tailwind CSS (TOBE와 동일)
- `design/` — Stitch로 만든 콘솔 화면 디자인 (HTML·스크린샷). 화면 구현은 이 디자인을 기준으로 한다

### 루트
- `docs/` — 기획 문서 (목록은 "참고 문서" 절)
- `.env`, `.env.example`, `CLAUDE.md`, `README.md`. 사이트 계정은 `.env`의 `SITE_<별칭 대문자, -는 _>_USERNAME/_PASSWORD`
- `sessions/` — 사이트 로그인 세션(`<별칭>.json`, storageState). 쿠키 원문이라 비밀값처럼 다룬다 (git 제외, next-pjt와 분리, G10)
- `run.ps1` — 에이전트와 콘솔 UI를 한 번에 실행

## 자주 쓰는 명령어

PowerShell 기준. 명령이 생기거나 바뀌면 여기에 추가한다.

### 전체 실행
- `.\run.ps1` — 에이전트 서버와 콘솔 UI를 함께 실행 (에이전트 서버 실행 명령이 정해지면 작성)

### 에이전트 (`agent/`)
- 의존성 설치: `agent\.venv\Scripts\python -m pip install -r agent/requirements.txt`, Playwright MCP: `npm install --prefix agent/mcp` (버전 고정 `@playwright/mcp@0.0.84`)
- 서버 실행: `cd agent; .venv\Scripts\python -m legacy2next --port 8000` (상태 확인: `GET /health`, API 문서: `/docs`). 덮어쓰기 옵션: `--log-dir`, `--checkpoint`, `--stub-step-ms`, `--cors-origin`, `--output-root`, `--session-dir`, `--auth-headless`(사용자 인증 브라우저 창을 띄우지 않음, E2E용), `--fake-llm`(Bedrock 대신 규칙 기반 가짜 LLM, E2E·자격 증명 없이 확인용)
- 테스트: `agent\.venv\Scripts\python -m pytest agent` (실제 Bedrock을 부르는 테스트는 건너뜀)
- 파생 파일 다시 만들기(저장된 원본만 사용, 브라우저 없이): `cd agent; .venv\Scripts\python -m legacy2next.crawl ../next-pjt/<별칭>/crawl`
- 실제 LLM 평가 샘플(RTR 등, 호출 비용 발생): `$env:L2N_LIVE="1"; agent\.venv\Scripts\python -m pytest agent -k live -s`
- 린트·포맷: `agent\.venv\Scripts\python -m ruff check agent`, `agent\.venv\Scripts\python -m ruff format agent`

### 콘솔 UI (`ui/`)
- 설치: `npm install --prefix ui`
- 개발 서버: `npm run dev --prefix ui`
- 빌드: `npm run build --prefix ui`
- 린트·포맷 검사: `npm run lint --prefix ui`, `npm run format:check --prefix ui`
- E2E 테스트(목업): `npm run test:e2e --prefix ui` (목업 API로 화면 흐름 검증, 포트 5179 사용)
- 콘솔은 기본으로 실제 에이전트 서버(`VITE_AGENT_API_URL`, 기본 `http://127.0.0.1:8000`)에 붙는다. 서버 없이 화면만 보려면 `VITE_USE_MOCK=1` (목업 진행 속도 `VITE_MOCK_TICK_MS`, 목업 상태는 새로고침하면 처음으로)
- 실제 서버 E2E: `npm run test:e2e:real --prefix ui` (에이전트 8010·콘솔 5180을 띄우고 임시 폴더에 기록, 스텁 그래프 전체 흐름 검증)

### 생성 결과물 (`next-pjt/<별칭>/`)
- 실행: `npm run dev --prefix next-pjt/<별칭>`

## 코딩 컨벤션

### 공통
- 주석·docstring·로그 메시지는 한국어, 식별자(변수·함수·파일명)는 영어
- 대상 사이트 URL·화면명·필드명을 코드에 하드코딩하지 않는다. 사이트별 값은 설정 파일에서 읽는다
- 비밀값(키·계정)은 `.env`에서만 읽는다

### Python (`agent/`)
- 모든 함수에 타입 힌트, 데이터 구조는 Pydantic 모델
- 포매터/린터: ruff
- 파일·함수: snake_case, 클래스: PascalCase

### TypeScript (`ui/`, `next-pjt/`)
- strict 모드, `any` 금지
- 포매터/린터: ESLint + Prettier
- 컴포넌트 파일: PascalCase(`AccountTable.tsx`), 그 외: camelCase
- 스타일은 Tailwind 유틸리티 클래스만 사용 (별도 CSS 파일·인라인 style 지양)
- 테스트 대상 요소에는 `data-testid`를 붙인다

## 작업 방식

- **기획 먼저**: 요구사항 인터뷰 → `docs/SERVICE.md` 작성 → 스킬·문서 세팅 → 구현 순서로 진행한다. 기획 없이 바로 코딩하지 않는다
- **작업 단위**: 구현은 작업 목록(T01, T02 …)으로 쪼개고, 작업 하나가 끝날 때마다 결과를 보고한 뒤 멈추고 확인을 받는다
- **완료 기준**: 테스트·빌드가 통과해야 완료로 보고한다. 실패하거나 건너뛴 단계는 그대로 보고한다
- **콘솔에서 확인하는 방법**: 작업 완료 보고에 "콘솔 UI(`ui/`)에서 확인하는 방법"을 함께 적는다. 띄울 서버와 명령, 열 주소, 누를 순서, 그때 보여야 하는 결과를 번호 목록으로 쓴다. 콘솔에서 아직 보이지 않는 작업이면 그렇다고 밝히고, 대신 확인할 방법(브라우저 주소, 명령)을 적는다
- **서버는 알아서 다시 띄운다**: 작업(Txx)이 끝나면 묻지 않고 확인에 필요한 서버(콘솔 5173, 에이전트 8000, 시험 사이트 8766 등)를 내렸다가 새 코드로 백그라운드에서 다시 띄운다. 완료 보고에 접속 주소와 응답 확인 결과를 적는다. E2E가 같은 포트를 쓰면 E2E 동안 내렸다가 끝난 뒤 다시 띄운다
- **UI 작업 순서**: Stitch로 디자인 생성 → 사용자 확인 → `design/`에 저장 → 디자인 기준으로 구현
- **문서 갱신**: 구조·명령어·스택이 바뀌면 CLAUDE.md의 해당 절도 같이 고친다
- **언어**: 보고·안내·질문은 모두 한국어로 한다

## 금지 사항 / 가드레일

- **비밀값 보호**: `.env`·계정 정보는 커밋하지 않고, 로그·생성 결과물·LLM 프롬프트에 남기지 않는다
- **생성 범위 제한**: 에이전트는 `next-pjt/<별칭>/` 밖에 파일을 쓰지 않는다
- **파괴적 명령 금지**: 폴더 삭제, `git reset --hard`, force push 같은 되돌리기 어려운 작업은 사용자 확인 후에만 실행한다

## Git 규칙

- **브랜치**: 작업은 `rebuild` 브랜치에서 하고, 제출할 때 `main`에 병합한다
- **커밋 메시지**: 한국어. 첫 줄에 요약, 빈 줄 다음에 변경 내용을 `-` 목록으로 적는다
  - 예: `T03 구현: 크롤 결과 저장` / `CLAUDE.md: 작업 방식 추가`
- **커밋 시점**: 사용자가 요청할 때만 커밋한다. 작업(Txx) 하나가 끝나면 커밋할지 묻는다
- **커밋 제외**: `.env`, `agent/.venv/`, `next-pjt/`, `logs/`, `node_modules/`
- **push**: 사용자가 요청할 때만 한다

## 참고 문서

- `docs/SERVICE.md` — 서비스 기획 (요구사항, 범위, 에이전트 구성). 구현 전에 먼저 읽는다
- `docs/TASKS.md` — 작업 목록(T01~)과 진행 상태
- `docs/GUARDRAILS.md` — 에이전트 가드레일 상세 (대상 사이트 접근 규칙, 입력·출력 검증)
- `docs/EVAL.md` — 평가셋 설명과 라운드별 결과 요약
- `docs/STITCH.md` — Stitch 디자인 작업 규칙 (저장 위치, 순서, Tailwind 맞추기). Stitch 작업 전에 읽는다
- `README.md` — 설치·실행 방법 (제출용)

문서가 추가되면 여기에 한 줄씩 더한다.