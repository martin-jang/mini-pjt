# CLAUDE.md — Mini PJT 작업 지침

SDS AX 교육 Day 8~10 Mini PJT 저장소입니다. **본인 업무의 반복 작업을 Agent로 만들어** 자동채점과 라이브 시연을 받습니다.
Day 1~7에서 만든 체인 · RAG · Agent · MCP · 가드레일 · Supervisor · 평가를 한 서비스로 엮는 것이 목표입니다.

## 프로젝트 개요

- **주제**: Legacy2Next — URL 하나로 레거시 웹 시스템을 크롤링·분석해 차세대 React 프론트엔드 POC를 1일 안에 생성하는 에이전트
- **대상 업무 / 반복 작업**: 레거시 현대화 과제 착수 시 화면 분석 → 공통 컴포넌트 설계 → 목업/POC 제작 (현재 1~2주 수작업)
- **사용자**: 소규모 AX 과제에 투입된 FDE, 결과물을 보는 고객사 현업·IT 담당자
- **성공 기준**: `SERVICE.md` §5 (인-아웃 세트 80%+, guardrail 100%, 빌드·Happy Path 흐름 검증 통과)

## 문서 맵 (작업 전 반드시 확인)

| 문서 | 역할 |
|---|---|
| `ASSIGNMENT.md` | 과제 요건·산출물 규약·채점 기준 (원본) |
| `SERVICE.md` | **기획서이자 설계의 단일 기준.** 범위·에이전트·도구·API 계약·평가 기준 |
| `docs/GUARDRAILS.md` | 가드레일 G1~G5 상세, HITL 지점 H1~H4 |
| `evaluation/README.md` | 인-아웃 세트 작성 가이드. 작성은 `test_queries.json`, 제출용 CSV는 `json_to_csv.py`로 변환 |
| `~/.gstack/projects/martin-jang-mini-pjt/ceo-review-2026-11-18.md` | CEO 리뷰 결정 원장(D1~D19), 일정표, 구현 작업 T1~T8 |

과제 설명: @ASSIGNMENT.md

- `SERVICE.md`와 다르게 구현해야 하면 **먼저 사용자에게 확인**하고, 확정되면 `SERVICE.md`를 함께 고칩니다. 문서와 구현이 어긋난 채로 두지 않습니다.
- `SERVICE.md`는 채점 대상 기획서입니다. 리뷰 메모·일정·작업 목록 같은 내용은 넣지 않습니다.

## 진행 순서와 일정

1. 기획(`SERVICE.md`) → 스킬·문서 세팅 → 구현 순서를 지킵니다. 단계마다 사용자 확인을 받습니다.
2. **필수 마감**: Day 9 16시 `/query` 질의 경로 동작, Day 9 18시 `evaluation/round1_report.md` 작성.
3. 일정이 밀리면 이 순서로 자릅니다 (사용자 승인 D17):
   1. Storybook 빌드 검증 → 스토리 파일만 작성
   2. Playwright 흐름 검증 → 정적 검사로 대체
   3. fastmcp MCP 서버 → LangChain 도구로 직접 구현
   4. 이체 Happy Path → 조회 Happy Path만 유지
4. 기능을 붙일 때마다 평가셋을 돌려 개선/회귀를 확인합니다 (Day 7 `run_eval` · `compare_eval`).

## 기술 스택 (교육 과정 고정 — 임의 변경 금지)

- LLM: `us.anthropic.claude-sonnet-4-5-20250929-v1:0` (Amazon Bedrock, `us-east-1`)
- 임베딩: `amazon.titan-embed-text-v2:0` (1024차원)
- 프레임워크: LangChain / LangGraph (`langgraph-supervisor`, `langchain-mcp-adapters`, `fastmcp`)
- 벡터DB: Chroma, `persist_directory="./chroma_db"`
- 체크포인터: `SqliteSaver` / `AsyncSqliteSaver`, 파일명 `checkpoints.sqlite`
- 패키지 기준: `sds-ax-training/requirements.txt` + ragas, playwright, fastapi (Python 3.14 환경에서 해석 확인됨)
- 생성 대상 앱: 고정 템플릿의 버전만 사용 (React + Vite + TS + React Router + antd + MSW + Storybook). LLM이 `package.json`을 수정하지 않습니다.

## 재사용할 Day 1~7 코드 (`sds-ax-training/dayNN/practice/starter/submission.py`)

| 용도 | 재사용 대상 |
|---|---|
| RAG 검색·근거 없음 판단 | Day 2 `build_retriever`, `assess_retrieval` |
| 입력 차단·PII·승인 판단 | Day 5 `input_guard`, `mask_pii`, `needs_approval` |
| Supervisor·라우팅·출력 판정 | Day 6 `build_supervisor`, `route_question`, `judge_output` |
| 트레이스·평가 | Day 7 `TraceCollector`, `run_eval`, `compare_eval` |

새 구조를 발명하기 전에 위 코드를 먼저 가져와 조합합니다.

## 코드 작성 규칙

- **모델은 함수 안에서 만듭니다.** `llm = llm or _default_llm()` 형태로 주입 가능하게 두고, 테스트는 가짜 모델로 실호출 없이 배선을 검증합니다.
- **도구는 결정적이어야 합니다.** 없는 값이나 빈 입력에도 예외 대신 안내 문자열을 반환합니다.
- **근거 없으면 답하지 않습니다.** 검색 결과가 부족하면 모델을 부르지 않고 "근거 없음"으로 응답합니다.
- **가드레일은 도구 경계와 코드 검사에서 강제합니다** (`docs/GUARDRAILS.md`). 프롬프트 지시만으로 막지 않습니다.
- **LLM은 생성 앱의 화면(`src/pages`, `src/components`)만 씁니다.** API 계약·MSW 핸들러·Happy Path `data-testid`는 코드로 결정적으로 생성합니다.
- **대상 사이트를 하드코딩하지 않습니다 (과적합 방지).** Crawler·Analyst·Builder·Verifier 코드와 프롬프트에 `ParaBank`라는 이름, URL, 화면명, 필드명 같은 사이트 고유 값을 넣지 않습니다. 사이트별 차이는 설정값(허용 도메인 목록, 데모 계정, 시작 URL)으로만 처리합니다. 평가셋이 ParaBank 기준이라 하드코딩하면 점수는 오르지만 다른 레거시에서는 동작하지 않는 코드가 됩니다. 사이트 고유 값은 설정 파일, `data/`, `evaluation/` 안에만 둡니다.
- **실패는 숨기지 않습니다.** 부분 성공은 `status="partial"`과 실패 원인을 응답·trace에 남깁니다.
- **주석과 docstring은 한국어로 상세하게** 씁니다. 도구 docstring에는 언제 쓰고 언제 쓰지 말아야 하는지 적습니다.
- 더미 데이터·합성 픽스처에는 "교육용 더미 데이터입니다"를 명시합니다. 실제 업무 데이터나 개인정보는 넣지 않습니다.

## 보안

- `.env`(AWS 키 등)는 절대 커밋하지 않습니다. 키 값은 `.env.example`에 빈 값으로만 둡니다.
- `chroma_db/`, `checkpoints.sqlite`, `.venv/`, `node_modules/`, `logs/`는 커밋하지 않습니다.
- 크롤링은 허용 도메인(`parabank.parasoft.com`)만. 상태 변경 제출은 승인된 이체 1회 외에는 하지 않습니다.

## Git / 제출

- 커밋, 푸시는 **사용자가 요청할 때만** 진행합니다.
- 최종 제출 커밋 메시지: `[제출] MiniPJT`
