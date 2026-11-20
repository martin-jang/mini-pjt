# HANDOFF.md — 다른 PC에서 이어서 작업하기

다른 PC(또는 새 Claude 세션)에서 이어서 작업할 때 이 문서를 먼저 읽는다. 기획·규칙의 기준은 `CLAUDE.md`, `docs/SERVICE.md`, `docs/TASKS.md`, `docs/GUARDRAILS.md`이고, 여기에는 **지금 어디까지 왔는지와 환경 준비**만 적는다.

마지막 갱신: 2026-11-20 (T07e 완료 시점)

## 1. 지금 상태

- 브랜치: `rebuild` (제출 때 `main`에 병합). 작업은 항상 `rebuild`에서
- 완료: T01~T07e (`docs/TASKS.md` 상태 표 참고)
- **다음 작업: T08** — 쓰기·위험 동작 승인(G1, 테스트 데이터 만들기 포함)과 네트워크 사후 확인. 완료 기준: 승인 요청이 콘솔에 뜨고 승인 없이 쓰기 요청 0건 (GRD-01)
- 그 다음: T09(개인정보 마스킹 Presidio) → 4단계(Analyst·Designer, T10~)

### 수집 에이전트(Explorer)에서 지금 실제로 동작하는 것

| 단계 | 상태 |
|---|---|
| 로그인 판별·ID/PW 자동 로그인·인증서/간편인증 사용자 넘김·세션 저장/재사용/만료 (T07a) | 실제 |
| 화면 원본 6종·파생 4종 저장, 저장본으로 파생 다시 만들기 (T07b, T07e) | 실제 |
| Map: 사이트맵 `graph.json`, 메뉴 영역 스크립트 메뉴 클릭 (T07c) | 실제 (조회만, LLM 없음) |
| Hypothesize·Walk: 유스케이스 후보, LLM이 동작을 골라 걷기, Flow Trace, LLM 없는 재실행 확인 (T07d) | 실제 |
| 빈 조회 결과 → 조건 넓혀 다시 조회 → 합성 데이터(`fixtures/`), 화면별 데이터 출처 (T07e) | 실제 |
| 쓰기 동작 승인 (T08) | 아직. 지금은 쓰기 동작을 실행하지 않고 "쓰기 동작 미승인"으로 멈춤 |
| 개인정보 마스킹 (T09) | 아직. **개인정보가 있는 실제 사이트는 T09 전에 돌리지 않는다** (원본이 가려지지 않고 저장됨) |
| Analyst·Designer·Builder·Verifier (T10~) | 스텁 (예시 데이터) |

### 사용자와 정한 진행 방식 (CLAUDE.md "작업 방식"에도 있음)

- 보고·안내·질문은 모두 **한국어**
- 작업(Txx) 하나가 끝나면 결과·검사 결과·콘솔 확인 방법을 보고하고 **멈춰서 확인**받는다. 여러 작업을 연달아 하지 않는다
- 작업이 끝나면 **묻지 않고** 서버(콘솔 5173, 에이전트 8000, 시험 사이트 8766)를 내렸다가 새 코드로 다시 띄우고 보고에 주소·응답 결과를 적는다
- **커밋·푸시는 사용자가 요청할 때만**. 커밋 메시지는 한국어, 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
- 제안·방향 설정을 요청받으면 `prior-art` 스킬로 기존 오픈소스를 먼저 찾는다
- UI 작업은 원칙상 Stitch 디자인 → 사용자 확인 → 구현. 다만 T04 이후 콘솔에 붙인 카드(인증 대기, 사이트맵, 흐름 걷기)는 기존 Callout·Card·표 디자인을 재사용했고 Stitch로 새로 그리지 않았다

## 2. 새 PC 준비

PowerShell 기준. 저장소 루트에서 실행한다.

1. 받기: `git clone https://github.com/martin-jang/mini-pjt.git; cd mini-pjt; git checkout rebuild`
2. Python 3.14 가상환경: `py -3.14 -m venv agent\.venv`, `agent\.venv\Scripts\python -m pip install -r agent/requirements.txt`
3. 콘솔: `npm install --prefix ui`, E2E 브라우저: `npx --prefix ui playwright install chromium`
4. Playwright MCP(에이전트가 띄우는 브라우저): `npm install --prefix agent/mcp`. MCP는 기본으로 Chrome을 쓰므로 Chrome이 설치되어 있어야 한다
5. `.env`: `.env.example`을 복사해 채운다 (커밋 금지)
   - `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (Bedrock 권한 계정)
   - `BEDROCK_MODEL_ID=global.anthropic.claude-sonnet-4-6` — 이 계정은 Sonnet 5.x와 bedrock-mantle 권한이 없다. 예전 `.env`에 5.x 모델 ID가 남아 있으면 바꾼다
   - `BEDROCK_FALLBACK_MODEL_ID=` (비움)
   - 로그인이 필요한 사이트 계정: `SITE_<별칭 대문자, -는 _>_USERNAME/_PASSWORD`
6. 확인: `agent\.venv\Scripts\python -m pytest agent` (실제 Bedrock 테스트는 건너뜀, 80개 넘게 통과해야 함), `npm run test:e2e --prefix ui`

git에 없는 것(새 PC에서 비어 있음, 정상): `next-pjt/`(생성 결과물), `logs/`, `checkpoints.sqlite`, `sessions/`(로그인 세션), `node_modules/`, `.venv/`, `.env`

## 3. 서버 띄우기 (확인용)

| 서버 | 명령 (저장소 루트) | 주소 |
|---|---|---|
| 콘솔 | `npm run dev --prefix ui` | http://localhost:5173 |
| 시험 사이트 | `agent\.venv\Scripts\python agent/tests/fixtures/site_server.py --port 8766` | http://127.0.0.1:8766 |
| 에이전트 | `cd agent; $env:SITE_IDPW_DEMO_USERNAME="tester"; $env:SITE_IDPW_DEMO_PASSWORD="fixture-pass-1234"; .venv\Scripts\python -m legacy2next --port 8000` | http://127.0.0.1:8000/health |

- 에이전트는 `.env`의 Bedrock 설정으로 실제 LLM을 쓴다. 자격 증명 없이 화면 흐름만 보려면 `--fake-llm`
- 시험 계정 `tester`/`fixture-pass-1234`는 시험 사이트 전용 값(실제 비밀값 아님). 별칭 `idpw-demo`로 `/idpw/home`을 요청하면 자동 로그인된다
- 실제 서버 E2E(`npm run test:e2e:real --prefix ui`)는 8766 포트를 직접 띄우므로, 돌리기 전에 시험 사이트를 내린다

### 시험 사이트 (`agent/tests/fixtures/site_server.py`)

| 경로 | 용도 |
|---|---|
| `/` | G2: 외부 링크·외부 리다이렉트·로그아웃 링크 |
| `/board.html`, `/board/view.html?id=N` | 전형적인 레거시 목록·상세, 검색(T07b~T07d) |
| `/archive.html` | 데이터가 하나도 없는 자료실 (T07e) |
| `/idpw/` | ID/PW 로그인 영역 (T07a) |
| `/cert/` | 간편인증 영역. 뜬 브라우저 창에서 "(시험용) 휴대폰에서 승인"을 누르면 로그인 |
| `POST /_test/approve`, `POST /_test/expire` | 간편인증 승인 흉내, 세션 만료 흉내 |

## 4. 검사 명령

- 에이전트: `agent\.venv\Scripts\python -m pytest agent`, `agent\.venv\Scripts\python -m ruff check agent`, `agent\.venv\Scripts\python -m ruff format --check agent`
- 실제 Bedrock 샘플(비용 발생): `$env:L2N_LIVE="1"; agent\.venv\Scripts\python -m pytest agent -k live -s` (Router RTR, 로그인 판별, 흐름 걷기)
- 콘솔: `npm run lint --prefix ui`, `npm run format:check --prefix ui`, `npm run build --prefix ui`, `npm run test:e2e --prefix ui`(목업), `npm run test:e2e:real --prefix ui`(실제 서버·실제 브라우저·가짜 LLM)

## 5. 열린 문제·메모

- 실제 서버 E2E에서 한 번, 간편인증 테스트 중 Playwright MCP 연결 끊김(`McpError: Connection closed`)으로 실패한 적이 있다. 이후 여러 번 통과했고 원인은 아직 모른다
- 실제 레거시 사이트(로컬 eGov 샘플, ParaBank)로는 아직 T07a~T07e를 돌려 보지 않았다
  - 로컬 eGov 샘플은 저장소 밖(`C:\Users\SDS\legacy-samples\`)에 설치한 전자정부 표준프레임워크 내부업무 템플릿이다. 다른 PC에서는 다시 설치해야 한다 (github `eGovFramework/egovframe-enterprise-business-template`, Tomcat에 올려 http://localhost:8080, 계정은 템플릿 기본 데모 계정)
  - eGov는 메뉴가 스크립트(onclick) 방식이라 Map의 메뉴 클릭이 실제로 통하는지 확인이 필요하다
- 흐름 걷기 한계: 재실행은 같은 역할+이름 요소가 여러 개면 첫 번째를 고른다. 걷다가 새로 닿은 화면은 저장하지만 `graph.json`에는 더하지 않는다. 등록·신청처럼 마지막이 쓰기 버튼인 흐름은 T08 전까지 "쓰기 동작 미승인"으로 끝난다
- 빈 결과 판정은 정해 둔 문구("결과가 없습니다" 등)로 한다. 문구 없이 표만 빈 화면은 LLM이 "데이터 없음"으로 포기할 때만 잡힌다
- 실행당 LLM 호출은 시험 사이트 기준 10~16회 (로그인 판별 1, 후보 1, 걷기 단계마다 1)
- Claude 메모리(`~/.claude/projects/.../memory/`)는 PC마다 따로라 저장소에 없다. 필요한 내용은 이 문서와 CLAUDE.md에 옮겨 두었다
