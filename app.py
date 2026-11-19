"""Legacy2Next API 진입점: POST /query

과제 표준 규약(ASSIGNMENT.md §4-2)을 따르되, HITL과 대화 이어가기를 위해 선택 필드
thread_id·approval을 추가합니다 (SERVICE.md "API 계약", 결정 D6).

  - 새 요청: {"question": "..."} → thread_id 를 새로 만들어 응답에 돌려줌
  - 승인이 필요하면: status="needs_approval" + pending(확인할 내용)
  - 이어가기: {"question": "...", "thread_id": "...", "approval": {"decision": "approve"}}
  - 없는 thread_id 로 승인 → 400, 이미 처리된 승인 재전송 → 무시하고 현재 상태 응답

실행:
    python app.py        (설정의 127.0.0.1:8000 에 바인딩, 가드레일 G5)
"""

from __future__ import annotations

import threading
import uuid
from typing import Any, Literal

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

app = FastAPI(title="Legacy2Next", version="0.2.0")


class Approval(BaseModel):
    """HITL 응답. decision은 approve/reject, edits는 사용자가 수정한 값(선택)."""

    decision: Literal["approve", "reject"]
    edits: dict[str, Any] | None = None


class QueryRequest(BaseModel):
    """과제 규약의 question에 선택 필드 2개를 더한 요청."""

    question: str = Field(..., min_length=1, description="사용자 질의")
    thread_id: str | None = Field(None, description="이어갈 대화(프로젝트) ID")
    approval: Approval | None = Field(None, description="needs_approval 응답에 대한 승인/거절")


class Context(BaseModel):
    doc_id: str
    text: str


class TraceStep(BaseModel):
    step: str
    input: Any = None
    output: Any = None
    elapsed_ms: int | None = None


class QueryResponse(BaseModel):
    """과제 규약(answer·contexts·trace)에 status·pending·thread_id·tools를 더한 응답."""

    answer: str
    contexts: list[Context] = []
    trace: list[TraceStep] = []
    status: Literal["ok", "needs_approval", "partial", "failed"] = "ok"
    pending: dict[str, Any] | None = None
    thread_id: str | None = None
    tools: list[str] = []


_graph = None
_lock = threading.Lock()


def get_graph():
    """그래프를 한 번만 만듭니다 (모델은 노드 안에서 필요할 때 생성)."""
    global _graph
    with _lock:
        if _graph is None:
            from src.agent import build_graph, default_checkpointer

            _graph = build_graph(default_checkpointer())
    return _graph


def _pending_interrupts(graph, config) -> list:
    snap = graph.get_state(config)
    return [i for t in (snap.tasks or []) for i in (t.interrupts or [])]


def _to_response(result: dict[str, Any], thread_id: str, graph, config) -> QueryResponse:
    interrupts = result.get("__interrupt__") or []
    if interrupts:
        pending = interrupts[0].value
        snap_values = graph.get_state(config).values
        return QueryResponse(answer=pending.get("message", "승인이 필요합니다."), status="needs_approval",
                             pending=pending, thread_id=thread_id, trace=snap_values.get("trace", []), contexts=[])
    return QueryResponse(answer=result.get("answer", ""), contexts=result.get("contexts", []),
                         trace=result.get("trace", []), status=result.get("status", "ok"),
                         thread_id=thread_id, tools=result.get("tools", []))


def run_query(req: QueryRequest, graph=None) -> QueryResponse:
    """/query 본체 (테스트에서 가짜 그래프를 넣을 수 있게 분리)."""
    from langgraph.types import Command

    graph = graph or get_graph()
    if req.approval is not None:
        if not req.thread_id:
            raise HTTPException(400, "approval 은 needs_approval 응답의 thread_id 와 함께 보내야 합니다.")
        config = {"configurable": {"thread_id": req.thread_id}}
        if not graph.get_state(config).values:
            raise HTTPException(400, f"존재하지 않는 thread_id 입니다: {req.thread_id}")
        if not _pending_interrupts(graph, config):
            values = graph.get_state(config).values  # 이미 처리된 승인: 무시하고 현재 상태 응답
            return QueryResponse(answer=values.get("answer", "이미 처리된 요청입니다."), status=values.get("status", "ok"),
                                 contexts=values.get("contexts", []), trace=values.get("trace", []),
                                 thread_id=req.thread_id, tools=values.get("tools", []))
        result = graph.invoke(Command(resume=req.approval.model_dump()), config)
        return _to_response(result, req.thread_id, graph, config)

    thread_id = req.thread_id or uuid.uuid4().hex[:12]
    config = {"configurable": {"thread_id": thread_id}}
    # 같은 thread 의 새 질문은 이전 실행 기록(trace/answer)을 덮고 새로 시작합니다
    result = graph.invoke({"question": req.question, "thread_id": thread_id, "trace": [], "contexts": [],
                           "answer": "", "status": "ok", "tools": []}, config)
    return _to_response(result, thread_id, graph, config)


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    return run_query(req)


# ──────────────────────────────────────────────────────────────────
# 작업(job) API: URL 하나 → 분석 → POC 생성 (작업 화면용, SERVICE.md "API 계약")
# /query 는 채점 규약 경로라 그대로 두고, 같은 노드를 묶은 작업 그래프를 백그라운드로 돌립니다.
# ──────────────────────────────────────────────────────────────────


class JobRequest(BaseModel):
    url: str = Field(..., min_length=1, description="현대화할 레거시 시스템 시작 URL")


class JobAction(BaseModel):
    """사용자 개입. approve/reject 는 승인 대기일 때, retry 는 실패·중단·부분 성공일 때만 받습니다."""

    action: Literal["approve", "reject", "retry"]
    edits: dict[str, Any] | None = None


_jobs = None


def get_jobs():
    global _jobs
    with _lock:
        if _jobs is None:
            from src.agent import build_pipeline_graph, default_checkpointer
            from src.jobs import JobManager

            _jobs = JobManager(lambda: build_pipeline_graph(default_checkpointer()))
    return _jobs


@app.get("/jobs/stages", include_in_schema=False)
def job_stages() -> list[dict[str, str]]:
    """화면에 그릴 단계 목록 (작업 시작 전에도 도식을 보여 주기 위해)."""
    from src.jobs import STAGES

    return STAGES


@app.post("/jobs", status_code=202)
def create_job(req: JobRequest) -> dict[str, Any]:
    """작업 시작. 이미 실행 중인 작업이 있으면 409. 진행은 GET /jobs/{id} 로 확인합니다."""
    try:
        return get_jobs().start(req.url.strip())
    except ValueError as e:
        raise HTTPException(409, str(e))


@app.get("/jobs/latest")
def latest_job() -> dict[str, Any] | None:
    """가장 최근 작업 (화면을 새로 고쳐도 진행 중인 작업을 이어서 보여 주기 위해)."""
    return get_jobs().latest()


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    job = get_jobs().get(job_id)
    if job is None:
        raise HTTPException(404, f"존재하지 않는 작업입니다: {job_id}")
    return job


@app.post("/jobs/{job_id}/action")
def job_action(job_id: str, req: JobAction) -> dict[str, Any]:
    try:
        return get_jobs().act(job_id, req.action, req.edits)
    except KeyError:
        raise HTTPException(404, f"존재하지 않는 작업입니다: {job_id}")
    except ValueError as e:
        raise HTTPException(409, str(e))


_UI_PATH = Path(__file__).parent / "static" / "index.html"


@app.get("/", include_in_schema=False)
def ui() -> FileResponse:
    """시연용 프롬프트 입력 화면 (static/index.html). 같은 출처의 POST /query 를 호출합니다."""
    return FileResponse(_UI_PATH, media_type="text/html; charset=utf-8")


@app.get("/examples", include_in_schema=False)
def examples() -> list[str]:
    """UI 예시 질의. 사이트 고유 값을 UI 코드에 넣지 않도록 평가셋(positive)에서 읽습니다.
    평가셋이 없거나 깨져 있으면 빈 목록을 돌려줍니다 (UI는 예시 없이 동작)."""
    import json

    path = Path(__file__).parent / "evaluation" / "test_queries.json"
    try:
        cases = json.loads(path.read_text(encoding="utf-8"))
        return [c["input"] for c in cases if c.get("category") == "positive"]
    except (OSError, ValueError, KeyError, TypeError):
        return []


if __name__ == "__main__":
    import uvicorn

    from src.config import settings

    import os

    server = settings()["server"]
    # 가드레일 G5: 로컬 시연 전용으로 127.0.0.1에만 바인딩.
    # 컨테이너 안에서는 포트 매핑을 위해 LEGACY2NEXT_HOST=0.0.0.0 으로 덮어쓰고,
    # 바깥 노출은 docker run -p 127.0.0.1:8000:8000 처럼 호스트의 루프백으로만 엽니다 (Dockerfile 참고).
    uvicorn.run(app, host=os.getenv("LEGACY2NEXT_HOST", server["host"]), port=server["port"])
