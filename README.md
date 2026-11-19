# 미니 PJT: Legacy2Next

> URL 하나로, 하루 만에, 실행되는 차세대 프론트엔드 POC

## 무엇을 푸나

소스·문서 없이 **URL과 테스트 계정만 받은 착수 초기**에, 레거시 웹 시스템을 크롤링·분석해 화면마다 미묘하게 다른 UI 변이를 표준으로 통일하고, 핵심 업무 흐름(Happy Path)이 실제로 동작하는 **React 차세대 프론트엔드 POC**(공통 컴포넌트 + Storybook + 화면)를 생성·검증합니다. FDE가 1~2주 걸리던 착수 초기 목업 작업을 하루 안으로 줄이는 것이 목표입니다. 상세 기획은 [`SERVICE.md`](SERVICE.md).

## 활용한 패턴 (Day 1~7)

| Day | 패턴 | 이 프로젝트에서 |
|---|---|---|
| Day 1 | LCEL·Pydantic 구조화 출력 | 화면 판단·변이 통일 결정·Happy Path·Judge 모두 `with_structured_output` + 검증 실패 시 재요청 (`src/llm.py`) |
| Day 2 | RAG (하이브리드·근거 판단) | 화면·통일 결정·Happy Path·컴포넌트 문서, 벡터+BM25 RRF, Day 2 `assess_retrieval` 재사용 → 근거 없으면 모델 미호출 (`src/retriever.py`) |
| Day 4 | 도구 다중·MCP | 자체 fastmcp 크롤러 서버(Playwright)를 `langchain-mcp-adapters`로 연결 (`mcp_server/crawler_server.py`) |
| Day 5 | 가드레일·HITL·미들웨어 | G1~G5(SSRF·읽기 전용·PII·인젝션·쓰기 범위)를 도구 경계에서 강제, `interrupt()` 승인 4곳, PII 마스킹·429 백오프 (`src/guardrails.py`, `docs/GUARDRAILS.md`) |
| Day 6 | 라우팅·출력 판정 | Day 6 `route_question` 처럼 규칙 기반 의도 라우팅 그래프 (분석/질의/생성/결과 수집/되묻기) (`src/agent.py`) |
| Day 7 | Plan-Execute·트레이스·평가 | 생성은 고정 단계 파이프라인, Day 7 `TraceCollector`로 단계별 trace, `run_eval`·`compare_eval` + RAGAS + LLM-as-Judge (`evaluation/run_eval.py`) |

## 아키텍처

```
POST /query ──▶ guard (입력 인젝션·URL SSRF 차단)
                 │
                 ▼
               route (규칙 기반 의도 분류)
   ┌─────────┬───┴──────┬───────────────┬──────────┬──────────┐
   ▼         ▼          ▼               ▼          ▼          ▼
 analyze   query     generate      submit_capture  clarify   run_info (생성 POC 실행 안내)
   │         │          │               │
   │  H1 로그인 승인   │ H4 덮어쓰기 → H3 Happy Path 확인     H2 이체 1회 승인
   ▼         ▼          ▼
 fastmcp 크롤러   RAG(Chroma+BM25)   생성 파이프라인 (고정 순서)
 (Playwright, 읽기 전용)              scaffold(고정 템플릿) → API 계약·MSW(결정적)
   │                                 → 공통 컴포넌트+스토리(LLM) → 화면(LLM)
   ▼                                 → 빌드·Storybook·정적 규칙·Playwright 흐름 검증
 인벤토리 → 변이 통일 → Happy Path    → 실패 시 2회 자가 수정 → 그래도 실패면 partial
   │
   └──▶ RAG 적재 (화면·통일 결정·Happy Path·컴포넌트)

체크포인트: SqliteSaver(checkpoints.sqlite) · trace: logs/trace.jsonl
```

## 실행 방법

```bash
# 1) Python 환경 (Python 3.14)
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium

# 2) 생성 앱 템플릿 의존성 (Node 20+, 1회)
cd templates/tobe-app && npm install && npx playwright install chromium && cd ../..

# 3) .env 작성 (.env.example 참고: AWS 자격증명, 데모 계정)

# 4) API 서버 (127.0.0.1:8000)
python app.py      # 또는 bash run.sh / powershell -ExecutionPolicy Bypass -File run.ps1
# 브라우저에서 http://127.0.0.1:8000/ 을 열면 프롬프트 입력 UI (승인/거절 버튼, 근거 문서·trace 펼쳐보기)
```

```bash
# 질의
curl -X POST 127.0.0.1:8000/query -H "Content-Type: application/json" \
     -d '{"question": "이체 화면에 어떤 입력 필드가 있어?"}'
# 분석 → needs_approval 이면 thread_id 와 approval 로 이어가기
curl -X POST 127.0.0.1:8000/query -H "Content-Type: application/json" \
     -d '{"question": "https://parabank.parasoft.com/parabank/index.htm 분석해줘"}'
curl -X POST 127.0.0.1:8000/query -H "Content-Type: application/json" \
     -d '{"question": "승인", "thread_id": "<응답의 thread_id>", "approval": {"decision": "approve"}}'
```

- 평가: `python evaluation/run_eval.py --round 1`
- 진행 점검(LLM 없이): `python scripts/check_progress.py`
- 비용 대시보드: `python scripts/cost_dashboard.py`
- 생성된 POC 실행: `cd output/parabank-next && npm run dev -- --mode mock` (http://localhost:5173, mock 모드여야 MSW 목업 API가 켜짐) / `npm run storybook` (http://localhost:6006)
- CSV 제출본 재생성: `python evaluation/json_to_csv.py` (평가셋 원본은 `evaluation/test_queries.json`)

```bash
# Docker (선택, 클린 환경 재현). .env 는 이미지에 넣지 않고 실행 시 전달, 호스트는 127.0.0.1 로만 노출
docker build -t legacy2next .
docker run --rm --env-file .env -p 127.0.0.1:8000:8000 legacy2next
```

**다른 레거시 붙이기 (코드 수정 없음)**: `config/settings.yaml`의 `extra_targets`에 허용 도메인·시작 URL·데모 계정 환경변수 이름·결과물 이름을 추가하고 `.env`에 계정을 넣습니다. 로컬에 띄운 샘플은 `allow_loopback_ports`에 포트를 명시한 경우에만 접근합니다. 로컬 eGov 샘플(`localhost:8080`)을 이 방식으로 붙였습니다.

## RAGAS 평가 결과

L1 질의응답 케이스 10건, 최종 (round 6, `evaluation/round2_report.md` §7)

- context_recall: 0.63
- context_precision: 0.88
- faithfulness: 0.90
- answer_relevancy: 0.79

| 지표 | Round 1 | Round 2 | Round 3 | Round 4 | Round 5 | **Round 6** |
|---|---|---|---|---|---|---|
| context_recall | 0.550 | 0.477 | 0.552 | 0.452 | 0.625 | **0.625** |
| context_precision | 0.708 | 0.733 | 0.808 | 0.708 | 0.808 | **0.883** |
| faithfulness | 0.709 | 0.809 | 0.836 | 0.683 | 0.829 | **0.897** |
| answer_relevancy | 0.411 | 0.602 | 0.693 | 0.611 | 0.730 | **0.787** |

## 인-아웃 세트 통과율 (자체 평가)

- 1차 (Day 9 종료): **14 / 20 통과 (70%)** (positive 5/8, negative 0/2, edge 5/5, guardrail 4/5)
- 2차 (Day 10 개선 후): 15 / 20 → round 3: 16 / 20 → 평가셋 22건으로 확장 후 **최종 round 6: 18 / 22 통과 (82%, guardrail 5/5, 회귀 0)**
- 개선폭: 통과율 **70% → 82% (+12%p)**, 같은 20건 기준 14 → 16건 (+2). 주요 개선 사항: 생성 파이프라인 연결(#5), 근거 없음 응답에 수집 범위·대체 행동 안내(#6·#7·#21), 덮어쓰기 확인 우선(#14), 개인정보 원문 요청 차단 안내(#13), 근거 밖 부연 금지(#9)
- round 4에서 두 번째 시스템 연동 후 회귀 3건(라우팅 오분류, 시스템 간 RAG 문서 섞임)을 발견해 round 5~6에서 수정 (`evaluation/round2_report.md` §7)
- 생성 품질(L3): 앱·Storybook 빌드 성공, Happy Path 흐름 2개(계좌 조회·계좌 이체) Playwright 통과, 라우트 커버리지 100%, 화면의 antd 직접 import 0건
- round 2에는 모델 전환(Sonnet 4.5 → 4.6) 효과가 섞여 있습니다. 회귀(#9·#13·#15)와 원인은 `evaluation/round2_report.md` §3

## 핵심 의사결정 2가지

**1. 생성 구간은 Supervisor 자유 위임이 아니라 고정 순서 파이프라인**
- 고른 것: 템플릿 → 계약·MSW → 공통 컴포넌트 → 화면 → 검증의 고정 순서 (`src/codegen/pipeline.py`).
- 버린 안: Supervisor가 서브 에이전트를 매번 골라 부르는 방식.
- 이유: 화면은 공통 컴포넌트가 있어야 만들 수 있고, 검증은 둘 다 있어야 의미가 있어 순서가 본질적으로 정해져 있습니다. 자유 위임은 순서를 매번 LLM이 다시 추론해 재현성이 떨어지고 비용만 늘어납니다. 대신 의도 라우팅(분석/질의/생성)은 규칙 기반 그래프로 나눴습니다.

**2. 크롤러는 공식 Playwright MCP 대신 자체 fastmcp 서버**
- 고른 것: 읽기 전용 수집과 설정에 등록된 1회 제출만 노출하는 자체 MCP 서버.
- 버린 안: 공식 Playwright MCP 서버.
- 이유: 공식 서버는 클릭·폼 입력을 모두 열어 두어 가드레일을 도구 밖(프롬프트)에서 걸어야 합니다. 자체 서버는 허용 도메인·SSRF·읽기 전용·이체 1회 제한을 **도구 경계에서 코드로** 강제해, 모델이 지시를 어겨도 실행 자체가 거부됩니다.

## 트라이앤에러 회고

**시도했지만 실패한 접근 · 왜 실패했는가**
- *LLM이 `package.json`까지 쓰게 하기* → MSW 3(v2 옵션 `onUnhandledRequest` 제거), TypeScript 7(`baseUrl` 제거), react-router 8(`react-router-dom` 습관) 등 최신 버전과 LLM 지식이 어긋나 빌드가 반복 실패. → 버전을 고정한 템플릿을 미리 빌드해 두고 LLM은 `src/`만 쓰게 바꿈. 흔한 실수(`react-router-dom` import, type-only import)는 템플릿 설정·별칭으로 흡수.
- *흐름(Flow)별 `data-testid`* → 두 흐름이 같은 로그인 화면을 지날 때 한 요소에 ID 두 개가 필요해 계약이 성립하지 않음. → 화면 단위 ID(`{slug}-page`, `{slug}-submit`, `{slug}-to-{대상}`) + 로그인 후 이동은 `?next=`.
- *임베딩 임계값 0.50으로 버튼 변이 묶기* → 화면 목적 문장이 조금 바뀌면 흔들림. 원인은 임계값이 아니라 레거시 라벨이 `:`·`and` 같은 조각으로 추출된 것. → 라벨 보정 + 실험값(같은 역할 0.55~0.79 / 다른 역할 ≤0.38) 사이 0.45.
- *합성 픽스처 화면도 RAG 문서로 적재* → 실제 화면을 복제한 것이라 한국어 질의 검색을 가로챔. → 픽스처는 통일 결정 문서만 적재.
- *Playwright 흐름 검증의 선택 목록 조작* → antd 드롭다운은 닫힌 뒤에도 DOM에 남아, 두 번째 선택 목록에서 숨은 첫 드롭다운 옵션을 누르려다 시간 초과. 화면 코드는 정상이었는데 2회 수정이 화면을 계속 다시 만들어 '구현 실패'로 바뀜. → 검증 스펙이 가장 최근에 열린 드롭다운만 보도록 수정, 라운드별 흐름 오류를 기록에 남김.
- *이체 결과 화면 캡처* → 제출 후 화면 갱신보다 캡처가 빨라 1회 기회를 소진. 두 번째 실제 제출은 하지 않고, 같은 화면에 숨겨진 결과 영역을 읽기 전용으로 수집(스냅샷에 사유 기록). 도구는 화면 변화를 기다리도록 수정.

- *ParaBank 하나로만 검증한 생성 코드* → 두 번째 대상(로컬 전자정부 표준프레임워크 내부업무 템플릿)을 붙이자 분석은 그대로 됐지만 생성 앱 빌드가 실패. 원인은 LLM이 아니라 결정적 계약 코드: ① 파일명이 같은 화면(`bbs/selectBoardList.do`·`bbs/admin/selectBoardList.do`)이 같은 이름이 되어 API 함수가 중복 선언, ② 한글 컬럼명은 영문 식별자가 없어 모두 `value`가 되고 라디오 버튼 묶음은 같은 name이 반복. LLM이 고칠 수 없는 파일이라 자가 수정 2회도 소용없었음. → 화면 목록 전체에서 겹치지 않는 이름을 정하는 규칙(상위 디렉터리 접두어 → 순번)과 키 중복 방지를 넣고, ParaBank 결과가 한 글자도 바뀌지 않는 것을 확인. 재생성 결과 status=ok(빌드·규칙·흐름 '공지사항 조회' 통과).
- *레거시 로그인 폼* → 제출 버튼 없이 `<a onclick="actionLogin()">`으로 제출하는 화면에서 로그인 실패. → 사이트별 선택자 없이 '제출 버튼 → 로그인 글자를 가진 클릭 요소 → Enter' 순서의 일반 규칙, 비밀번호 입력란이 사라질 때까지 대기.
- *"생성된 POC 페이지에 접속하고 싶어"* → 콘솔 UI 시연 중 `생성`이라는 글자 때문에 POC를 다시 만듦. → 생성 '지시' 동사(생성해·만들어줘·다시 생성)와 결과물을 '보는' 질문(접속·주소·실행 방법)을 구분하고, 후자는 LLM 없이 결과물 위치·실행 명령·화면 주소를 안내(`run_info`).

**최종 채택한 접근 · 왜 그것으로 갔는가**
- 결정적으로 만들 수 있는 것(계약·MSW·testid·라우트·플레이스홀더·Playwright 스펙)은 코드로, 판단·창작이 필요한 것(화면 성격·통일 결정·컴포넌트·화면)만 LLM으로. 실패 지점을 줄이고 검증을 결정적으로 만들기 위해서입니다.
- 정답 라벨은 사람이 결과를 보고 쓰지 않고 합성 픽스처의 주입 목록에서 자동 생성 (평가가 결과에 끌려가지 않게).

**남은 한계 · 향후 개선 방향**
- 정량 평가(인-아웃 세트·RAGAS·L2)는 ParaBank와 합성 픽스처 기준입니다. 두 번째 대상(로컬 eGov 샘플)은 분석→생성이 끝까지 동작하는지만 확인했고(화면 31개·업무 12개, POC status=ok), 정답 라벨이 없어 정확도는 측정하지 않았습니다. 관리 화면(코드·권한 관리 등)은 업무 화면이 아니라고 판단되어 POC 대상에서 빠졌습니다.
- MSW mock 은 제출 값 검증·결과 표시까지만 흉내 내고, 잔액 같은 업무 상태 변화는 재현하지 않습니다.
- Bedrock 일일 토큰 한도에 걸리면 생성이 멈춥니다(파이프라인은 한도 초과를 감지해 즉시 실패로 보고). 개발 중 us-east-1 Sonnet 4.5 한도를 넘어, Day 10에는 사용자 지시로 `global.anthropic.claude-sonnet-4-6`(ap-northeast-2)으로 전환했습니다. 모델은 `config/settings.yaml`의 `llm` 항목에서 바꿉니다.
- LLM-as-Judge 판정은 실행마다 흔들릴 수 있습니다.

## 핵심 코드 위치

- `src/agent.py:380` — 메인 에이전트 그래프 (`build_graph`), `:60` 의도 라우팅, `:93` 입력 가드, `:147` 분석 노드, `:237` 생성 노드, `:320` 실행 안내 노드
- `app.py:101` — `POST /query` 본체 (`run_query`, HITL 이어가기), `:209` 시연용 UI (`static/index.html`)
- `src/tools.py` · `mcp_server/crawler_server.py` · `src/crawler_core.py` — MCP 크롤러 도구 (`:393` 로그인 포함 수집, `:423` 범용 로그인 제출)
- `src/retriever.py:266` — RAG 질의응답 (`answer_question`), `:229` 근거 판단
- `src/analyst/` — 인벤토리 · 변이 클러스터링 · 통일 결정 · Happy Path (`naming.py:26` 화면 이름 충돌 방지)
- `src/codegen/pipeline.py:33` — 생성 파이프라인 (`generate_poc`), `contracts.py:141` 결정적 API 계약, `components.py`·`pages.py`·`verifier.py`
- `src/guardrails.py:41` — 가드레일 G1 URL 검사 (`:127` 개인정보 요청 감지), G2~G5
- `src/config.py:38` — 대상 사이트 설정 (`targets`, `:72` 로컬 샘플 예외)
- `evaluation/run_eval.py` — 평가 하네스
