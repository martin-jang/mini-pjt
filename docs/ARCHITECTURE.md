# ARCHITECTURE · Legacy2Next 내부 구조도

`SERVICE.md` §3과 `docs/GUARDRAILS.md`를 그림으로 옮긴 문서입니다. GitHub, VS Code(Markdown Preview Mermaid Support), [mermaid.live](https://mermaid.live)에서 바로 렌더링됩니다.

> 범례: 실선 = 구현 완료(T01~T08), 점선 테두리 = 구현 예정(T09~). 구현 현황은 `tasks/README.md` 기준입니다.

---

## 1. 전체 시스템 구성

```mermaid
flowchart TB
    User(["FDE / 고객사 담당자"])

    subgraph API["app.py · FastAPI (127.0.0.1)"]
        Q["POST /query<br/>question · thread_id · approval"]
        G0["G0 입력 검사<br/>Day5 input_guard"]
    end

    subgraph AGENT["src/agent.py · LangGraph"]
        SUP{"Supervisor<br/>의도 라우팅"}
        CK[("checkpoints.sqlite<br/>SqliteSaver")]
    end

    subgraph SUBS["서브 에이전트"]
        CR["Crawler"]
        AN["Analyst<br/>src/analyst/"]
        RAG["RAG 질의<br/>src/retriever.py"]
        CB["Component Builder"]
        PB["Page Builder"]
        VF["Verifier"]
    end

    subgraph MCP["mcp_server/crawler_server.py · fastmcp"]
        T1["crawl_site"]
        T2["capture_page"]
        T3["login_with_demo_account"]
        T4["submit_once_and_capture"]
        PW["Playwright"]
    end

    subgraph STORE["데이터"]
        SNAP[("data/snapshots/<br/>PII 마스킹")]
        FIX[("data/fixtures/<br/>합성 변이")]
        CHROMA[("chroma_db/<br/>Titan Embed v2")]
        ART[("분석 산출물 JSON<br/>inventory · patterns ·<br/>decisions · happy_paths")]
    end

    subgraph GEN["생성 앱"]
        TPL["templates/tobe-app<br/>고정 템플릿"]
        OUT["output/{프로젝트}/<br/>React · antd · MSW · Storybook"]
    end

    LEGACY(["레거시 사이트<br/>config/settings.yaml 허용 도메인"])
    LLM(["Bedrock<br/>claude-sonnet-4-5"])

    User --> Q --> G0 --> SUP
    SUP <--> CK
    SUP -- 분석 --> CR
    SUP -- 질의 --> RAG
    SUP -- 생성 --> AN

    CR -- langchain-mcp-adapters --> MCP
    T1 & T2 & T3 & T4 --> PW --> LEGACY
    MCP --> SNAP
    SNAP --> AN
    FIX --> AN
    AN --> ART
    ART --> CHROMA
    SNAP --> CHROMA
    RAG --> CHROMA

    AN --> CB --> PB --> VF
    TPL -- 복사 --> OUT
    CB & PB -- write_project_file --> OUT
    VF -- build · 검사 · 흐름 검증 --> OUT

    AN -.-> LLM
    RAG -.-> LLM
    CB -.-> LLM
    PB -.-> LLM

    classDef todo stroke-dasharray: 5 5
    class SUP,CK,RAG,CB,PB,VF,CHROMA,OUT todo
```

---

## 2. 요청 처리와 HITL 이어가기 (시퀀스)

한 번의 생성 요청이 HITL 지점마다 `needs_approval`로 끊기고, 같은 `thread_id` + `approval`로 체크포인트에서 이어집니다.

```mermaid
sequenceDiagram
    autonumber
    actor U as 사용자
    participant A as /query (FastAPI)
    participant G as input_guard
    participant S as Supervisor (LangGraph)
    participant C as SqliteSaver
    participant W as 서브 에이전트

    U->>A: {"question": "URL 을 차세대로 전환해줘"}
    A->>G: 입력 검사
    alt 인젝션·정책 위반
        G-->>A: 차단
        A-->>U: "요청을 처리할 수 없습니다"
    else 통과
        G->>S: question
        S->>S: route_question → 생성
        S->>W: Crawler → Analyst
        W-->>S: interrupt(H1 로그인 승인)
        S->>C: 상태 저장
        S-->>A: pending
        A-->>U: status=needs_approval, pending, thread_id
    end

    U->>A: {thread_id, approval: approve}
    A->>S: Command(resume=approval)
    C-->>S: 체크포인트 복원
    S->>W: 이어서 실행 (H2 → H3 → H4 동일 패턴)
    W-->>S: 결과 + 근거 + trace
    S-->>A: answer, contexts, trace
    A-->>U: status=ok | partial | failed
```

---

## 3. 생성 파이프라인 (고정 파이프라인 + 자가 수정)

```mermaid
flowchart TD
    START(["생성 요청"]) --> H4{"H4 기존 결과물 있음?"}
    H4 -- 있음 --> H4A{"덮어쓰기 승인?"}
    H4A -- 거절 --> STOP1(["새 프로젝트명 안내"])
    H4A -- 승인 --> CRAWL
    H4 -- 없음 --> CRAWL

    subgraph CRAWLER["Crawler (읽기 전용)"]
        CRAWL["crawl_site<br/>공개 화면"] --> H1{"H1 데모 계정<br/>로그인 승인?"}
        H1 -- 승인 --> LOGIN["login_with_demo_account<br/>로그인 후 화면 수집"]
        H1 -- 거절 --> PUB["공개 화면만"]
        LOGIN --> H2{"H2 이체 1회<br/>실행 승인?"}
        H2 -- 승인 --> SUBMIT["submit_once_and_capture<br/>결과 화면 수집"]
        H2 -- 거절 --> NOTX["이체 흐름 제외"]
    end

    SUBMIT & NOTX & PUB --> MASK["mask_pii → 스냅샷 저장"]
    MASK --> ZERO{"수집 0페이지?"}
    ZERO -- 예 --> FAIL1(["failed: URL·계정 확인 안내"])
    ZERO -- 아니오 --> INV

    subgraph ANALYST["Analyst"]
        INV["build_screen_inventory"] --> PAT["extract_ui_patterns"]
        PAT --> CLU["cluster_ui_variants"]
        CLU --> DEC["decide_unification"]
        INV --> HP["derive_happy_paths<br/>+ data-testid"]
    end

    DEC & HP --> H3{"H3 통일 보류 항목<br/>+ Happy Path 확인"}
    H3 -- 전부 거절 / 0개 --> FAIL2(["failed: 근거 부족"])
    H3 -- 승인 / edits 반영 --> SCAF

    subgraph BUILD["Builder"]
        SCAF["scaffold_project<br/>고정 템플릿 복사"] --> CONTRACT["API 계약 · MSW 핸들러<br/>코드로 결정적 생성"]
        CONTRACT --> CB["Component Builder<br/>공통 컴포넌트 + 스토리"]
        CB --> PB["Page Builder<br/>Happy Path 화면 구현<br/>나머지 = 구현 예정"]
    end

    PB --> VF

    subgraph VERIFY["Verifier"]
        VF["run_build<br/>check_component_rules<br/>run_happy_path_check"]
    end

    VF -- 통과 --> OK(["status=ok"])
    VF -- 실패 · 2회 미만 --> BACK{"원인 에이전트"}
    BACK -- 컴포넌트 --> CB
    BACK -- 화면 --> PB
    VF -- 2회 실패 --> PH["실패 화면만<br/>플레이스홀더로 교체 · 재빌드"]
    PH --> PART(["status=partial<br/>실패 화면 · 에러 요약"])
```

---

## 4. Analyst 내부 (변이 정규화)

```mermaid
flowchart LR
    SNAP[("스냅샷<br/>+ 픽스처")] --> INV["inventory.py<br/>화면·필드·액션·전환"]
    INV --> J1[/"screen_inventory.json"/]

    INV --> VAR["variants.py<br/>요소 수집 → 클러스터링<br/>라벨 임베딩 + 맥락 + 구조"]
    VAR --> UNI["unification.py<br/>표준 추론"]

    subgraph RULE["표준 추론 순서"]
        R1["① 다수결<br/>Happy Path 가중치"] --> R2["② 현대 UX · antd 관례"] --> R3["③ 기존 표준과 일관성"]
    end
    UNI --- RULE

    UNI --> CLS{"결정 분류"}
    CLS -- 의미 같음 · 표현만 다름 --> D1["통일"]
    CLS -- 업무 의미 있는 차이 --> D2["변형 유지 → prop"]
    CLS -- 근거 부족 · 동작 바뀜 --> D3["보류 → HITL H3"]
    D1 & D2 & D3 --> J2[/"unification_decisions.json<br/>변이 · 표준 · 근거 · 확신도"/]

    INV --> HPP["happy_path.py<br/>전환 그래프 + 화면 성격"]
    HPP --> J3[/"happy_paths.json<br/>단계 ID = data-testid"/]

    J1 & J2 & J3 --> SC["score.py<br/>L2 정답 비교"]
    GOLD[("evaluation/golden/")] --> SC
```

---

## 5. 질의응답 (RAG) 경로

```mermaid
flowchart LR
    Q["질문"] --> R["하이브리드 검색<br/>BM25 + Chroma<br/>Day2 build_retriever"]
    R --> DOCS["화면 1개 = 문서 1개<br/>통일 결정 1건 = 문서 1개"]
    DOCS --> AS{"assess_retrieval<br/>근거 충분?"}
    AS -- 아니오 --> NO(["근거 없음 응답<br/>LLM 호출 안 함"])
    AS -- 예 --> DATA["크롤링 텍스트를<br/>데이터 블록으로 감쌈 · G4"]
    DATA --> LLM["Bedrock 답변 생성"]
    LLM --> JUDGE["judge_output<br/>출력 판정"]
    JUDGE --> RES(["answer + contexts + trace"])
```

---

## 6. 가드레일 강제 지점

```mermaid
flowchart TB
    IN["POST /query"] --> G0["G0 input_guard<br/>직접 인젝션 차단"]
    G0 --> SUP["Supervisor"]

    SUP --> CRAWL["Crawler 도구 진입부"]
    CRAWL --- G1["G1 허용 도메인 · SSRF<br/>DNS 해석 후 IP 재검사 · 리다이렉트 재검사"]
    CRAWL --- G2["G2 읽기 전용<br/>이체 1회만 예외 · HITL · 세션당 1회"]
    CRAWL --- G3["G3 mask_pii<br/>저장·적재 이전"]
    CRAWL --- G4a["G4 크롤링 텍스트 = 데이터 블록"]

    SUP --> BLD["Builder · Verifier"]
    BLD --- G5["G5 쓰기 범위 output/{프로젝트}/src/<br/>package.json · .. 거부 · 덮어쓰기 HITL"]
    BLD --- G4b["G4 금지 패턴 정적 검사<br/>dangerouslySetInnerHTML · 외부 URL · eval"]
    BLD --- DEP["허용 목록 밖 import 차단"]

    G1 & G2 & G3 & G4a & G5 & G4b & DEP -.-> CODE["src/guardrails.py<br/>공통 검사 (도구 경계에서 강제)"]
```

---

## 7. 응답 상태 전이

```mermaid
stateDiagram-v2
    [*] --> running: POST /query
    running --> blocked: input_guard 차단
    running --> needs_approval: interrupt (H1~H4)
    needs_approval --> running: approval 수신 (같은 thread_id)
    running --> ok: 빌드 · 흐름 검증 통과
    running --> partial: 자가 수정 2회 실패 → 플레이스홀더
    running --> failed: 0페이지 · 근거 부족 · 일시 장애
    blocked --> [*]
    ok --> [*]
    partial --> [*]
    failed --> [*]
```

---

## 8. 파일 ↔ 구성 요소 매핑

| 구성 요소 | 파일 | 상태 |
|---|---|---|
| API 진입점 | `app.py` | 스텁 (T11에서 그래프 연결) |
| 설정 (사이트별 값) | `config/settings.yaml`, `src/config.py` | ✅ |
| 가드레일 | `src/guardrails.py`, `src/reuse/day05_guard.py` | ✅ |
| 크롤러 MCP 서버 | `mcp_server/crawler_server.py`, `src/crawler_core.py` | ✅ |
| Analyst | `src/analyst/inventory.py` · `variants.py` · `unification.py` · `happy_path.py` · `score.py` | ✅ (happy_path는 T09) |
| LLM 팩토리 | `src/llm.py` | ✅ |
| Supervisor · HITL | `src/agent.py` | T11 |
| RAG | `src/retriever.py` | T10 |
| 계약 · MSW · Builder · Verifier | `src/codegen/` | T14~T17 |
| 고정 템플릿 | `templates/tobe-app/` | ✅ |
