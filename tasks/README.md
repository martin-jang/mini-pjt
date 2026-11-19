# tasks · 구현 작업 목록

`SERVICE.md`를 30분~1시간 단위 작업으로 나눈 목록입니다. 작업 하나 = 파일 하나(`T01-*.md` …)이고, 각 파일에 목표·작업 항목·산출물·완료 기준이 있습니다.

## 진행 규칙

- 번호 순서대로 진행합니다. 의존 작업이 끝나지 않으면 시작하지 않습니다.
- 작업이 끝나면 **완료 기준을 실제로 실행해 확인**한 뒤 체크합니다.
- 기능을 붙일 때마다 평가셋을 돌려 회귀를 확인합니다 (T12 이후).
- 사이트 고유 값(ParaBank 이름·URL·화면명)은 `config/` · `data/` · `evaluation/`에만 둡니다 (`CLAUDE.md` 과적합 방지 규칙).

## 목표 프로젝트 구조

```
mini-pjt/
├── app.py                      # POST /query (FastAPI, 127.0.0.1)
├── config/settings.yaml        # 허용 도메인·시작 URL·데모 계정 키 이름 (사이트별 값은 여기만)
├── src/
│   ├── agent.py                # Supervisor·의도 라우팅·HITL 그래프
│   ├── tools.py                # MCP 클라이언트 + 분석·생성 도구
│   ├── retriever.py            # RAG 적재·검색
│   ├── guardrails.py           # G1~G5 공통 검사
│   ├── analyst/                # 인벤토리·변이·통일·Happy Path
│   └── codegen/                # 계약·MSW 생성, Builder, Verifier
├── mcp_server/crawler_server.py  # fastmcp 크롤러 (Playwright)
├── templates/tobe-app/         # 고정 TOBE 템플릿 (버전 pin)
├── data/  snapshots/ fixtures/ # 크롤링 스냅샷, 합성 변이 픽스처
├── evaluation/                 # test_queries, golden/, run_eval.py, round*_report.md
├── output/parabank-next/       # 백업 생성 결과물
├── tests/                      # 가짜 LLM 단위 테스트
├── requirements.txt · run.sh · README.md
```

## 작업 순서와 일정

| # | 작업 | 예상 | 일정 | 의존 |
|---|---|---|---|---|
| T01 | [프로젝트 골격과 `/query` 스텁](T01-project-skeleton.md) | 30분 | Day 9 오전 | — |
| T02 | [고정 TOBE 템플릿](T02-tobe-template.md) | 60분 | Day 9 오전 | — |
| T03 | [가드레일 공통 모듈](T03-guardrails.md) | 45분 | Day 9 오전 | T01 |
| T04 | [fastmcp 크롤러 서버 (읽기 전용)](T04-mcp-crawler.md) | 60분 | Day 9 오전 | T03 |
| T05 | [이체 1회 HITL 도구 + 실제 크롤링](T05-transfer-hitl-crawl.md) | 45분 | Day 9 오전 | T04 |
| T06 | [합성 변이 픽스처 + L2 정답 라벨](T06-fixtures-golden.md) | 60분 | Day 9 점심 전후 | T05 |
| T07 | [Analyst ① 화면 인벤토리](T07-analyst-inventory.md) | 45분 | Day 9 오후 | T05 |
| T08 | [Analyst ② 변이 클러스터링·통일 결정](T08-analyst-unification.md) | 60분 | Day 9 오후 | T06, T07 |
| T09 | [Analyst ③ Happy Path + data-testid](T09-analyst-happy-path.md) | 30분 | Day 9 오후 | T07 |
| T10 | [RAG 적재·검색·근거 없음](T10-rag.md) | 45분 | Day 9 오후 | T07, T08 |
| T11 | [Supervisor·의도 라우팅·HITL API](T11-supervisor-api.md) | 60분 | Day 9 오후 | T10, T09 |
| — | **체크포인트: Day 9 16시 `/query` 질의 경로 동작** | | | |
| T12 | [평가 하네스 + RAGAS](T12-eval-harness.md) | 60분 | Day 9 오후 | T11 |
| T13 | [round1 실행·리포트](T13-round1.md) | 30분 | Day 9 저녁 | T12 |
| — | **체크포인트: Day 9 18시 `round1_report.md`** | | | |
| T14 | [API 계약·MSW 결정적 생성](T14-contracts-msw.md) | 45분 | Day 10 오전 | T02, T09 |
| T15 | [Component Builder + 스토리](T15-component-builder.md) | 60분 | Day 10 오전 | T08, T14 |
| T16 | [Page Builder + 라우트·플레이스홀더](T16-page-builder.md) | 45분 | Day 10 오전 | T15 |
| T17 | [Verifier·자가 수정·partial](T17-verifier.md) | 60분 | Day 10 오전 | T16 |
| T18 | [생성 E2E + 백업 결과물](T18-generate-e2e.md) | 30분 | Day 10 오전 | T17 |
| T19 | [round2 + 개선폭 비교](T19-round2.md) | 30분 | Day 10 오후 | T18 |
| T20 | [README·시연 준비·제출](T20-readme-submit.md) | 45분 | Day 10 오후 | T19 |

**합계 약 15시간 45분 [estimated]**

## ⚠️ 시간 초과 경고

작업 단위로 쪼개서 다시 합산하니 **약 15.75시간**입니다. CEO 리뷰 때의 추정(약 11시간)보다 큽니다. 사용 가능한 시간은 약 12.5시간입니다(Day 9 8h + Day 10 오전 3h + Day 10 13~15시 일부). **약 3시간이 부족합니다.**

- Day 9 작업(T01~T13): 약 10.5시간 → 8시간 안에 끝내려면 2.5시간을 줄여야 합니다.
- Day 10 작업(T14~T20): 약 5.25시간 → 오전 3시간 + 오후 일부로는 빠듯합니다.

그래서 아래 절단 순서(사용자 승인 D17)를 **처음부터 계획에 반영해 두는 것**을 권장합니다.

| 절단 단계 | 줄어드는 작업 | 절약 [estimated] |
|---|---|---|
| 1 Storybook 빌드 검증 → 스토리 파일만 | T02 Storybook 빌드 설정, T17 `build-storybook` | 약 30분 |
| 2 Playwright 흐름 검증 → 정적 검사 | T17 흐름 검증, T02 Playwright 설정 | 약 45분 |
| 3 fastmcp 서버 → LangChain 도구 직접 구현 | T04 서버화, T05 MCP 클라이언트 | 약 30분 |
| 4 이체 Happy Path 제외 | T05 이체 HITL, T09·T16 이체 단계 | 약 45분 |

모두 적용하면 약 2.5시간이 줄어듭니다. 그래도 부족한 시간은 각 작업의 "줄일 수 있는 부분"으로 메웁니다.

## 진행 상황

| 작업 | 상태 | 메모 |
|---|---|---|
| T01 | ✅ 완료 | `/query` 스텁 200, 필수값 누락 422 |
| T02 | ✅ 완료 | build·build-storybook·Playwright(MSW) 통과. 고정 버전은 T02 파일 기록 |
| T03 | ✅ 완료 | `tests/test_guardrails.py` 9건 통과 (Day 5 코드는 `src/reuse/`에 복사) |
| T04 | ✅ 완료 | 고유 화면 21개 수집, MCP 도구 4종, SSRF 차단 확인 |
| T05 | ✅ 완료 | 이체 1회 실행($1) 확인. 결과 화면은 숨은 결과 영역을 읽기 전용으로 수집 (스냅샷에 사유 기록) |
| T06 | ✅ 완료 | 픽스처 7화면, 변이 그룹 6개(변형 유지 2), 정답 업무 화면 13개 |
| T07 | ✅ 완료 | 화면 recall 100%(실제 13/13, 픽스처 7/7). 업무 화면 기준에 인증 화면 포함으로 수정. 필드 recall은 정답이 같은 추출 결과에서 나와 참고용 |
| T08 | ✅ 완료 | 픽스처 기준 변이 그룹 recall 100%, 결정 정확도 100%, 과잉 통일 0건. 실제 사이트는 진짜 변이 거의 없음(예상대로) |
| T09 | ✅ 완료 | 흐름 2개(계좌 조회, 계좌 이체) 2회 연속 동일. 근거 없는 흐름(가입·거래검색)은 코드 검증에서 제외. T04 공개 화면 덮어쓰기 버그 수정 |
| T10 | ✅ 완료 | 질의 12건 중 10건 기대대로 (남은 2건은 공통 컴포넌트 질문 → T15 후 근거 생김). 한국어 화면명·머리글 추가, 픽스처 화면 문서 제외, 버튼 임계값 0.45·라벨 보정 |
| T11 | ✅ 완료 | **16시 체크포인트 충족.** /query 실서버 시나리오 9개 통과 (질의·분석 H1·생성 H3·이체 H2·되묻기·400). 생성 노드는 승인까지만, 코드 생성은 T14~ 연결. 기본 모드를 스냅샷 재생으로 전환 |
| T12 | ✅ 완료 | 하네스(Day 7 run_eval + LLM Judge + 결정적 검사) + RAGAS 4종 + L2·L4. reference 10건은 evaluation/golden/references.json 에만 (CSV 미포함). 스모크 3+2건 확인 |
| T13 | ✅ 완료 | **18시 체크포인트 충족.** round1 14/20(70%), guardrail 4/5, L2 전부 목표 달성, RAGAS faithfulness 0.709·relevancy 0.411. 개선 Top5는 round1_report.md |
| T14~ | ⏸ 대기 | 사용자 확인 후 진행 |

## 체크포인트 (반드시 지킴)

- **Day 9 16시**: `/query`로 질의(L1)가 근거와 함께 답하고, 근거가 없으면 "근거 없음"으로 응답 (T11 완료)
- **Day 9 18시**: `evaluation/round1_report.md` 작성 (T13 완료)
- **Day 10 15시**: 최종 제출
