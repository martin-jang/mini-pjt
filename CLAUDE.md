# CLAUDE.md — Mini PJT 작업 지침

## 프로젝트 개요

- **주제**: Legacy2Next — URL 하나로 레거시 웹 시스템을 분석해 차세대 React 프론트엔드 POC를 1일 안에 생성하는 에이전트
- **대상 업무 / 반복 작업**: 레거시 현대화 과제 착수 시 화면 분석 → 공통 컴포넌트 설계 → 목업/POC 제작 (현재 1~2주 수작업)

## 기술 스택 / 환경

- **런타임**: Python 3.14 (`agent/.venv`), Node v26
- **에이전트**: LangGraph 고정 그래프 (Router + 단계별 노드, `interrupt()`로 사용자 승인), 체크포인트 SqliteSaver
- **LLM / 임베딩**: AWS Bedrock Claude Sonnet 4.5 / Titan Embeddings v2
- **RAG**: Chroma
- **화면 수집**: Playwright MCP (`microsoft/playwright-mcp`)
- **개인정보 마스킹**: Presidio (`presidio-analyzer`, `presidio-anonymizer`)
- **UI 디자인**: Stitch MCP로 화면 디자인 생성
- **생성물(TOBE)**: React + Vite + TypeScript + React Router + Tailwind CSS, Storybook, Playwright 검증
- **API 서버**: FastAPI (`/query` 단일 진입점)
- **비밀값**: `.env`에서만 읽음 (`.env.example` 제공)

## 디렉터리 구조

루트는 역할별로 세 폴더로 나눈다.

### `agent/` — 에이전트 구동 코드
- `.venv/` — Python 가상환경 (git 제외)
- 하위 구조는 기획(SERVICE.md)을 확정한 뒤 정하고, 정해지면 여기에 추가한다

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
- `.env`, `.env.example`, `CLAUDE.md`, `README.md`
- `run.ps1` — 에이전트와 콘솔 UI를 한 번에 실행

## 자주 쓰는 명령어

PowerShell 기준. 명령이 생기거나 바뀌면 여기에 추가한다.

### 전체 실행
- `.\run.ps1` — 에이전트 서버와 콘솔 UI를 함께 실행 (에이전트 서버 실행 명령이 정해지면 작성)

### 에이전트 (`agent/`)
- 의존성 설치: `agent\.venv\Scripts\python -m pip install -r agent/requirements.txt`
- 서버 실행: (구현 후 추가)
- 테스트: `agent\.venv\Scripts\python -m pytest agent`

### 콘솔 UI (`ui/`)
- 설치: `npm install --prefix ui`
- 개발 서버: `npm run dev --prefix ui`
- 빌드: `npm run build --prefix ui`

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