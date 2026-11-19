# CLAUDE.md — Mini PJT 작업 지침

## 프로젝트 개요

- **주제**: Legacy2Next — URL 하나로 레거시 웹 시스템을 분석해 차세대 React 프론트엔드 POC를 1일 안에 생성하는 에이전트
- **대상 업무 / 반복 작업**: 레거시 현대화 과제 착수 시 화면 분석 → 공통 컴포넌트 설계 → 목업/POC 제작 (현재 1~2주 수작업)

## 기술 스택 / 환경

- **런타임**: Python 3.14 (`.venv`), Node v26
- **에이전트**: LangGraph (Supervisor + 서브 에이전트), 체크포인트 SqliteSaver
- **LLM / 임베딩**: AWS Bedrock Claude Sonnet 4.5 / Titan Embeddings v2
- **RAG**: Chroma
- **크롤러**: Playwright, fastmcp로 만든 자체 MCP 서버
- **UI 디자인**: Stitch MCP로 화면 디자인 생성
- **생성물(TOBE)**: React + Vite + TypeScript + React Router + Tailwind CSS, Storybook, Playwright 검증
- **API 서버**: FastAPI (`/query` 단일 진입점)
- **비밀값**: `.env`에서만 읽음 (`.env.example` 제공)

## 디렉터리 구조

루트는 역할별로 세 폴더로 나눈다.

### `agent/` — 에이전트 구동 코드
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
- `docs/` — SERVICE.md, GUARDRAILS.md 등 기획 문서
- `.env`, `.env.example`, `CLAUDE.md`, `README.md`