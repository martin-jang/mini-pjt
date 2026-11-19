"""메인 에이전트 그래프 (T11): 입력 가드 → 의도 라우팅 → 분석 / 질의 / 생성 / 이체 결과 수집 / 되묻기.

- 라우팅은 Day 6 route_question 처럼 LLM 없이 규칙으로 합니다 (같은 질문엔 언제나 같은 경로, 비용 0).
- 승인이 필요한 지점(HITL H1~H4, docs/GUARDRAILS.md)에서는 LangGraph interrupt()로 멈추고,
  SqliteSaver 체크포인트에 상태를 저장합니다. 다음 /query 호출의 thread_id + approval 로 이어갑니다.
- 상태(state)에는 trace 를 누적해, 멈췄다 이어가도 전체 실행 기록이 한 응답에 담깁니다.
사이트 고유 값은 없습니다. 도메인은 질문의 URL 또는 설정의 시작 URL에서 얻습니다.
"""

from __future__ import annotations

import asyncio
import json
import re
import sqlite3
from typing import Any, Literal, TypedDict
from urllib.parse import urlparse

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from src.config import path as cfg_path
from src.config import settings, target_for
from src.guardrails import PII_REFUSAL, check_url, input_guard, mask_pii, pii_request
from src.tracing import emit, step

Intent = Literal["analyze", "query", "generate", "submit_capture", "clarify", "run_info", "blocked"]
URL_RE = re.compile(r"https?://[^\s'\"<>]+", re.IGNORECASE)


class AgentState(TypedDict, total=False):
    question: str
    thread_id: str
    intent: Intent
    url: str | None
    domain: str
    answer: str
    contexts: list[dict[str, Any]]
    trace: list[dict[str, Any]]
    status: Literal["ok", "needs_approval", "partial", "failed"]
    tools: list[str]


# ──────────────────────────────────────────────────────────────────
# 라우팅 (규칙 기반, Day 6 패턴)
# ──────────────────────────────────────────────────────────────────

_GENERATE = re.compile(r"(poc|생성|만들어|구현해|전환해|변환해|코드로|프론트엔드)", re.IGNORECASE)
_ANALYZE = re.compile(r"(분석|크롤링|수집|스캔|살펴)", re.IGNORECASE)
_SUBMIT = re.compile(r"(결과\s*화면).{0,10}(수집|캡처|가져)", re.IGNORECASE)
# 생성된 POC를 '보는/여는' 방법을 묻는 질문. "생성된 POC 페이지에 접속하고 싶어" 가 생성 의도로 잘못 가던 문제 수정
#  - 강한 표현(접속·띄우기·실행 방법·열어 보기)은 그 자체로 실행 안내
#  - 약한 표현(주소·URL·링크)은 결과물 문맥(POC·생성된·만든·결과물·앱·스토리북)이 있을 때만
#    ("계좌 상세 화면 URL이 계좌번호마다 다른데…" 같은 분석 질문을 가로채지 않도록)
_ACCESS_STRONG = re.compile(r"(접속|띄우|띄워|열어\s*보|여는\s*법|실행\s*(방법|하려면|법|명령)|스토리북\s*(어디|어떻게))",
                            re.IGNORECASE)
_ACCESS_WEAK = re.compile(r"(주소|url|링크)", re.IGNORECASE)
_RESULT_CTX = re.compile(r"(poc|생성된|만든|만들어진|결과물|생성\s*결과|차세대\s*앱|스토리북|storybook)", re.IGNORECASE)
# 생성 '지시'로 볼 수 있는 동사형 (과거형·관형형 '생성된/만들어진'은 제외)
_GEN_COMMAND = re.compile(r"(생성\s*해|생성\s*하|만들어\s*(줘|주|봐|라)|구현\s*해|전환\s*해|변환\s*해|다시\s*생성)",
                          re.IGNORECASE)
_VAGUE = re.compile(r"^(그|저|이)\s*(화면|거|것|페이지)\s*(좀\s*)?(바꿔|변경|고쳐|수정)", re.IGNORECASE)


def route_question(question: str) -> Intent:
    """질문 의도를 규칙으로 정합니다. LLM을 호출하지 않습니다.

    - 대상이 불분명한 지시("그 화면 바꿔줘") → clarify (임의 화면을 골라 실행하지 않음)
    - 결과 화면 수집 요청 → submit_capture (H2 승인 필요)
    - 생성된 POC 접속·실행 방법 질문(생성 지시 동사 없음) → run_info (재생성하지 않음)
    - POC/생성/전환 → generate
    - URL이 있거나 분석·크롤링 요청 → analyze
    - 그 외 → query (RAG 질의응답)
    """
    q = (question or "").strip()
    if _VAGUE.search(q):
        return "clarify"
    if _SUBMIT.search(q):
        return "submit_capture"
    asks_access = _ACCESS_STRONG.search(q) or (_ACCESS_WEAK.search(q) and _RESULT_CTX.search(q))
    if asks_access and not _GEN_COMMAND.search(q) and not URL_RE.search(q):
        return "run_info"
    if _GENERATE.search(q):
        return "generate"
    if URL_RE.search(q) or _ANALYZE.search(q):
        return "analyze"
    return "query"


def _default_domain() -> str:
    return (urlparse(settings()["target"]["start_url"]).hostname or "").lower()


# ──────────────────────────────────────────────────────────────────
# 노드
# ──────────────────────────────────────────────────────────────────


def guard_node(state: AgentState) -> AgentState:
    """G4 직접 인젝션 차단 + 질문 속 URL의 G1 검사. 막히면 이유를 안내하고 끝냅니다."""
    trace = list(state.get("trace", []))
    q = state["question"]
    with step(trace, "input_guard", q, thread_id=state.get("thread_id")) as out:
        blocked, reason = input_guard(q)
        url = (URL_RE.search(q) or [None])[0]
        url_ok, url_reason = check_url(url) if url else (True, "")
        out["output"] = reason if blocked else (url_reason if not url_ok else "통과")
    if blocked:
        return {"intent": "blocked", "trace": trace, "status": "ok", "contexts": [],
                "answer": "요청을 처리할 수 없습니다. 내부 지침 노출이나 지시 무시 요청에는 답하지 않습니다. "
                          "레거시 화면 분석·질의·POC 생성 요청은 계속 도와드릴 수 있습니다."}
    if pii_request(q):  # G3: 개인정보 원문 요청은 모델을 부르지 않고 안내
        return {"intent": "blocked", "trace": trace, "status": "ok", "contexts": [], "answer": PII_REFUSAL}
    if url and not url_ok:
        return {"intent": "blocked", "trace": trace, "status": "ok", "contexts": [],
                "answer": f"허용되지 않은 주소라 수집하지 않았습니다. {url_reason} "
                          "허용된 도메인의 URL로 다시 요청해 주세요."}
    domain = (urlparse(url).hostname or "").lower() if url else state.get("domain") or _default_domain()
    return {"url": url, "domain": domain, "trace": trace}


def route_node(state: AgentState) -> AgentState:
    trace = list(state["trace"])
    with step(trace, "route", state["question"], thread_id=state.get("thread_id")) as out:
        intent = route_question(state["question"])
        out["output"] = intent
    return {"intent": intent, "trace": trace}


def _approve(kind: str, message: str, detail: dict[str, Any]) -> dict[str, Any]:
    """HITL: interrupt 로 멈추고 승인 응답(dict)을 돌려받습니다. 응답 형식: {"decision": "approve"|"reject", ...}."""
    answer = interrupt({"type": kind, "message": message, **detail})
    return answer if isinstance(answer, dict) else {"decision": str(answer)}


def query_node(state: AgentState) -> AgentState:
    from src.retriever import answer_question

    trace = list(state["trace"])
    with step(trace, "retrieve_screens", state["question"], thread_id=state.get("thread_id")) as out:
        r = answer_question(state["question"], domain=state.get("domain"))  # 현재 대상 시스템 문서만 검색
        out["output"] = {"grounded": r["grounded"], "docs": [c["doc_id"] for c in r["contexts"]],
                         "assessment": r["assessment"]["reason"]}
    return {"answer": r["answer"], "contexts": r["contexts"], "trace": trace, "status": "ok",
            "tools": ["retrieve_screens"]}


def _has_snapshots(domain: str) -> bool:
    d = cfg_path("snapshots") / domain
    return d.is_dir() and any(d.glob("*.json"))


def analyze_node(state: AgentState) -> AgentState:
    """분석: (H1 로그인 승인) → 크롤링 → 인벤토리 → 변이·통일 → Happy Path → RAG 적재."""
    from src.analyst.happy_path import derive_happy_paths
    from src.analyst.inventory import build_screen_inventory
    from src.analyst.unification import decide_unification
    from src.retriever import index_documents
    from src.tools import call_crawler

    trace, tools = list(state["trace"]), []
    domain = state["domain"]
    start_url = state.get("url") or target_for(domain)["start_url"]
    replay = settings()["crawl"]["snapshot_mode"] == "replay" and _has_snapshots(domain)

    h1 = _approve("login", "로그인 후 화면까지 수집하려면 공개된 데모 계정으로 로그인해야 합니다. 진행할까요?",
                  {"domain": domain, "action": "login_with_demo_account"})
    login_ok = h1.get("decision") == "approve"

    with step(trace, "crawl_site", {"url": start_url, "login_approved": login_ok, "replay": replay},
              thread_id=state.get("thread_id")) as out:
        if replay:
            out["output"] = "스냅샷 재생 모드: 저장된 화면 사용"
        else:
            r = asyncio.run(call_crawler("crawl_site", start_url=start_url, login_approved=login_ok))
            out["output"] = r
        tools += ["crawl_site", "capture_page"] + (["login_with_demo_account"] if login_ok else [])

    with step(trace, "build_screen_inventory", domain, thread_id=state.get("thread_id")) as out:
        inv = build_screen_inventory(domain)
        out["output"] = {k: inv.get(k) for k in ("screen_count", "business_count", "error")}
        tools.append("build_screen_inventory")
    if inv.get("error") or not inv.get("screen_count"):
        return {"trace": trace, "tools": tools, "status": "failed", "contexts": [],
                "answer": "수집된 화면이 없어 분석을 진행할 수 없습니다. URL과 데모 계정 설정을 확인해 주세요."}

    with step(trace, "decide_unification", domain, thread_id=state.get("thread_id")) as out:
        un = decide_unification(domain)
        out["output"] = un.get("summary")
        tools += ["cluster_ui_variants", "decide_unification"]
    with step(trace, "derive_happy_paths", domain, thread_id=state.get("thread_id")) as out:
        hp = derive_happy_paths(domain)
        out["output"] = [f["name"] for f in hp.get("flows", [])]
        tools.append("derive_happy_paths")
    with step(trace, "index_documents", domain, thread_id=state.get("thread_id")) as out:
        # 분석이 끝난 모든 도메인을 함께 다시 적재 (한 도메인만 넣으면 다른 도메인 문서가 사라짐)
        analyzed = sorted({p.parent.name for p in cfg_path("analysis").glob("*/screen_inventory.json")} | {domain})
        out["output"] = index_documents(analyzed)

    biz = [s for s in inv["screens"] if s["is_business"]]
    login_n = sum(s["requires_login"] for s in biz)
    lines = [f"{domain} 분석을 마쳤습니다. 수집한 화면 {inv['screen_count']}개 중 업무 화면은 {len(biz)}개입니다 "
             f"(로그인 필요 {login_n}개, 공개 {len(biz) - login_n}개).",
             "업무 화면: " + ", ".join(f"{s['title_ko'] or s['title']}{'(로그인)' if s['requires_login'] else ''}"
                                     for s in biz),
             f"UI 변이 그룹 {un.get('group_count', 0)}개: {un.get('summary')}",
             "핵심 업무 흐름: " + (", ".join(f["name"] for f in hp.get("flows", [])) or "없음")]
    if not login_ok:
        lines.append("로그인을 승인하지 않아 공개 화면만 기준으로 했습니다.")
    return {"answer": "\n".join(lines), "contexts": [], "trace": trace, "tools": tools, "status": "ok"}


def submit_capture_node(state: AgentState) -> AgentState:
    """H2: 설정에 등록된 폼을 1회 제출해 결과 화면을 수집합니다 (가드레일 G2의 유일한 예외)."""
    from src.tools import call_crawler

    trace = list(state["trace"])
    specs = target_for(state.get("domain")).get("submit_once") or []
    if not specs:
        return {"trace": trace, "status": "ok", "contexts": [],
                "answer": "이 사이트에는 1회 제출이 허용된 폼이 설정되어 있지 않습니다. "
                          "읽기 전용 정책(G2)에 따라 폼을 제출하지 않습니다."}
    spec = specs[0]
    h2 = _approve("submit_once", f"'{spec.get('name')}' 폼을 실제로 1회 제출해 결과 화면을 수집합니다. "
                                 "서버 상태가 바뀌는 작업입니다. 진행할까요?",
                  {"form": spec.get("form_id"), "values": spec.get("values")})
    if h2.get("decision") != "approve":
        return {"trace": trace, "status": "ok", "contexts": [],
                "answer": "승인하지 않아 제출하지 않았습니다. 결과 화면 없이 진행합니다."}
    with step(trace, "submit_once_and_capture", spec.get("name"), thread_id=state.get("thread_id")) as out:
        r = asyncio.run(call_crawler("submit_once_and_capture", name=spec.get("name"), approved=True))
        out["output"] = r
    text = json.dumps(r, ensure_ascii=False) if not isinstance(r, str) else r
    if "이미 1회" in text:
        answer = "이 폼은 이미 1회 제출했습니다. 정책상 다시 제출하지 않고, 저장된 결과 화면을 사용합니다."
    elif "error" in text:
        answer = f"결과 화면을 수집하지 못했습니다: {mask_pii(text)[:200]}"
    else:
        answer = "승인에 따라 1회 제출하고 결과 화면을 수집했습니다."
    return {"answer": answer, "trace": trace, "status": "ok", "contexts": [], "tools": ["submit_once_and_capture"]}


def generate_node(state: AgentState) -> AgentState:
    """생성: H3(보류 항목 + Happy Path 확인) → H4(덮어쓰기) → 생성 파이프라인 (T14~T18에서 연결)."""
    from src.analyst.happy_path import load_happy_paths
    from src.analyst.unification import load_decisions

    trace = list(state["trace"])
    domain = state["domain"]
    flows = load_happy_paths(domain)
    if not flows:
        return {"trace": trace, "status": "failed", "contexts": [],
                "answer": "핵심 업무 흐름이 없어 POC를 생성할 수 없습니다. 먼저 URL 분석을 요청해 주세요."}
    project = target_for(domain)["project_name"]
    out_dir = cfg_path("output") / project
    rel_dir = f"output/{out_dir.name}"
    overwrite = False
    # H4 를 H3 보다 먼저: 기존 결과물이 있으면 무엇을 덮어쓰는지부터 확인받습니다 (round1 #14 개선)
    if out_dir.exists():
        h4 = _approve("overwrite", f"기존 결과물 {rel_dir} 이(가) 있습니다. 이 폴더를 덮어쓰고 다시 생성할까요?",
                      {"path": rel_dir})
        if h4.get("decision") != "approve":
            return {"trace": trace, "status": "ok", "contexts": [],
                    "answer": f"기존 결과물 {rel_dir} 을(를) 유지하고 생성하지 않았습니다. 다른 프로젝트명으로 요청해 주세요."}
        overwrite = True
    held = [d for d in load_decisions(domain) if d["decision"] == "hold"]
    h3 = _approve("happy_path_confirm", "아래 핵심 업무 흐름으로 POC를 생성합니다. 보류된 통일 항목이 있으면 함께 확인해 주세요.",
                  {"happy_paths": [{"flow_id": f["flow_id"], "name": f["name"],
                                    "steps": [s["screen_title"] for s in f["steps"]]} for f in flows],
                   "held_decisions": [{"group_id": d["group_id"], "role": d["role"], "reason": d["reason"]}
                                      for d in held]})
    if h3.get("decision") != "approve":
        return {"trace": trace, "status": "ok", "contexts": [],
                "answer": "핵심 업무 흐름을 승인하지 않아 생성을 중단했습니다. 수정할 흐름을 알려 주세요."}

    from src.codegen.pipeline import generate_poc
    from src.retriever import index_documents

    with step(trace, "generate_poc", {"project": rel_dir, "overwrite": overwrite},
              thread_id=state.get("thread_id")) as out:
        tid = state.get("thread_id")
        report = generate_poc(domain, project, overwrite_approved=True,
                              log=lambda msg, *_: emit(tid, "log", "generate_poc", {"message": str(msg)}),
                              progress=lambda st, name, detail: emit(tid, "stage", name, {"state": st, **detail}))
        out["output"] = {k: report.get(k) for k in ("status", "error", "fallback_components", "failed_pages",
                                                    "timings_s")}
    tools = ["derive_happy_paths", "scaffold_project", "write_project_file"]
    if report.get("error"):
        return {"trace": trace, "status": "failed", "contexts": [], "tools": tools,
                "answer": f"POC 생성에 실패했습니다: {report['error']}"}
    c = report["checks"]
    with step(trace, "run_build", rel_dir, thread_id=state.get("thread_id")) as out:
        out["output"] = {"app": c["app_build"], "storybook": c["storybook_build"]}
    with step(trace, "check_component_rules", rel_dir, thread_id=state.get("thread_id")) as out:
        out["output"] = {"ok": c["rules_ok"], "violations": len(c["rule_violations"]), "route_coverage": c["route_coverage"]}
    with step(trace, "run_happy_path_check", rel_dir, thread_id=state.get("thread_id")) as out:
        out["output"] = {k: v["ok"] for k, v in c["happy_path"].items()}
    tools += ["run_build", "check_component_rules", "run_happy_path_check"]
    # 생성된 공통 컴포넌트 매핑을 질의응답 근거로 적재 (모든 분석 도메인 재적재)
    analyzed = sorted({p.parent.name for p in cfg_path("analysis").glob("*/screen_inventory.json")} | {domain})
    index_documents(analyzed)

    flow_lines = [f"- {name}: {'통과' if r['ok'] else '실패'}" for name, r in c["happy_path"].items()]
    rules_text = "통과" if c["rules_ok"] else f"위반 {len(c['rule_violations'])}건"
    lines = [f"POC를 {rel_dir} 에 생성했습니다 (status={report['status']}, 소요 {report['timings_s'].get('total')}초).",
             f"- 앱 빌드: {'성공' if c['app_build'] else '실패'} / Storybook 빌드: {'성공' if c['storybook_build'] else '실패'}",
             f"- 공통 컴포넌트 {len(report['components'])}개: {', '.join(report['components'])}",
             f"- Happy Path 화면 {len(report['happy_path_pages'])}개 구현, 나머지 {len(report['placeholder_pages'])}개는 '구현 예정' 화면",
             f"- 라우트 커버리지 {c['route_coverage']:.0%}, 정적 규칙 {rules_text}",
             "- Happy Path 흐름 검증:", *flow_lines]
    if report["fallback_components"] or report["failed_pages"]:
        lines.append(f"- 자가 수정 2회 후에도 실패해 대체한 항목: 컴포넌트 {report['fallback_components']}, "
                     f"화면 {report['failed_pages']} ('구현 실패' 화면)")
    lines += _run_lines(rel_dir)
    return {"trace": trace, "status": report["status"], "contexts": [], "tools": tools, "answer": "\n".join(lines)}


def _run_lines(rel_dir: str) -> list[str]:
    """생성된 POC를 띄우는 방법 (템플릿 고정값: Vite 5173, Storybook 6006, MSW 는 mock 모드)."""
    return ["생성된 POC 보기 (생성 에이전트는 코드를 만들고 검증까지만 하며, 서버는 직접 띄워야 합니다):",
            f"- 앱: cd {rel_dir} → npm run dev -- --mode mock → http://localhost:5173/ "
            "(mock 모드여야 목업 API가 켜집니다)",
            f"- Storybook: cd {rel_dir} → npm run storybook → http://localhost:6006/"]


def run_info_node(state: AgentState) -> AgentState:
    """생성된 POC의 위치·실행 명령·접속 주소를 결정적으로 안내합니다 (LLM 호출 없음, 재생성하지 않음).

    언제 쓰나: "생성된 POC 어떻게 봐?", "접속 주소 알려줘" 처럼 결과물을 여는 방법을 물을 때.
    언제 쓰지 않나: 새로 생성하라는 지시 → generate.
    """
    trace = list(state["trace"])
    project = target_for(state.get("domain"))["project_name"]
    rel_dir = f"output/{project}"
    report_path = cfg_path("output") / project / "generation_report.json"
    with step(trace, "read_generation_report", rel_dir, thread_id=state.get("thread_id")) as out:
        report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else None
        out["output"] = report and {k: report.get(k) for k in ("status", "happy_path_pages")}
    if not report:
        return {"trace": trace, "status": "ok", "contexts": [], "tools": ["read_generation_report"],
                "answer": f"아직 생성된 POC가 없습니다 ({rel_dir}). 먼저 분석한 뒤 'POC 생성해줘'라고 요청해 주세요."}
    lines = [f"생성된 POC는 {rel_dir} 에 있습니다 (status={report.get('status')}).", *_run_lines(rel_dir)]
    routes = _happy_routes(cfg_path("output") / project, report.get("happy_path_pages") or [])
    if routes:
        lines.append("Happy Path 화면 주소: " + ", ".join(f"{t} http://localhost:5173{p}" for p, t in routes))
    return {"trace": trace, "status": "ok", "contexts": [], "tools": ["read_generation_report"],
            "answer": "\n".join(lines)}


def _happy_routes(project_dir, pages: list[str]) -> list[tuple[str, str]]:
    """생성 앱 routes.tsx 에서 Happy Path로 구현된 화면(generation_report 의 happy_path_pages)의 경로를 읽습니다."""
    p = project_dir / "src" / "routes.tsx"
    if not p.exists():
        return []
    wanted = {x.lower() for x in pages}
    return [(path_, title) for path_, title, element in
            re.findall(r"path: '([^']+)', title: '([^']+)', element: <(\w+)", p.read_text(encoding="utf-8"))
            if element.lower().removesuffix("page") in wanted]


def clarify_node(state: AgentState) -> AgentState:
    from src.analyst.inventory import load_inventory

    trace = list(state["trace"])
    titles = [s.title_ko or s.title for s in load_inventory(state["domain"]) if s.is_business][:8]
    with step(trace, "clarify", state["question"], thread_id=state.get("thread_id")) as out:
        out["output"] = titles
    return {"trace": trace, "status": "ok", "contexts": [],
            "answer": "어떤 화면을 말씀하시는지 알려 주세요. 임의로 화면을 골라 바꾸지 않습니다. "
                      f"후보 화면: {', '.join(titles) or '(먼저 URL 분석이 필요합니다)'}"}


# ──────────────────────────────────────────────────────────────────
# 그래프
# ──────────────────────────────────────────────────────────────────


def _after_guard(state: AgentState) -> str:
    return END if state.get("intent") == "blocked" else "route"


def _after_route(state: AgentState) -> str:
    return state["intent"]


def build_graph(checkpointer=None):
    g = StateGraph(AgentState)
    g.add_node("guard", guard_node)
    g.add_node("route", route_node)
    for name, fn in [("query", query_node), ("analyze", analyze_node), ("generate", generate_node),
                     ("submit_capture", submit_capture_node), ("clarify", clarify_node),
                     ("run_info", run_info_node)]:
        g.add_node(name, fn)
        g.add_edge(name, END)
    g.add_edge(START, "guard")
    g.add_conditional_edges("guard", _after_guard, {"route": "route", END: END})
    g.add_conditional_edges("route", _after_route,
                            {k: k for k in ("query", "analyze", "generate", "submit_capture", "clarify", "run_info")})
    return g.compile(checkpointer=checkpointer)


def _after_guard_pipeline(state: AgentState) -> str:
    if state.get("intent") == "blocked":
        return END
    if not state.get("url"):
        return "no_url"
    return "analyze"


def _after_analyze(state: AgentState) -> str:
    return END if state.get("status") == "failed" else "generate"


def no_url_node(state: AgentState) -> AgentState:
    """작업(job) 경로는 URL이 꼭 있어야 합니다. 없으면 분석하지 않고 안내합니다."""
    return {"status": "failed", "contexts": [],
            "answer": "분석할 URL을 찾지 못했습니다. http:// 또는 https:// 로 시작하는 주소를 입력해 주세요."}


def build_pipeline_graph(checkpointer=None):
    """URL 하나로 끝까지 가는 작업 그래프: 입력 가드 → 분석 → 생성.

    언제 쓰나: 작업 화면(POST /jobs)에서 URL만 받아 POC까지 한 번에 만들 때. 승인 지점(H1·H4·H3)은
    analyze/generate 노드의 interrupt 를 그대로 쓰므로 /query 경로와 같은 가드레일이 적용됩니다.
    언제 쓰지 않나: 자연어 질의·개별 명령 → build_graph (POST /query).
    """
    g = StateGraph(AgentState)
    g.add_node("guard", guard_node)
    g.add_node("no_url", no_url_node)
    g.add_node("analyze", analyze_node)
    g.add_node("generate", generate_node)
    g.add_edge(START, "guard")
    g.add_conditional_edges("guard", _after_guard_pipeline, {"analyze": "analyze", "no_url": "no_url", END: END})
    g.add_conditional_edges("analyze", _after_analyze, {"generate": "generate", END: END})
    g.add_edge("no_url", END)
    g.add_edge("generate", END)
    return g.compile(checkpointer=checkpointer)


def default_checkpointer():
    from langgraph.checkpoint.sqlite import SqliteSaver

    conn = sqlite3.connect(str(cfg_path("checkpoints")), check_same_thread=False)
    return SqliteSaver(conn)
