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

from fastapi import FastAPI, HTTPException
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


if __name__ == "__main__":
    import uvicorn

    from src.config import settings

    server = settings()["server"]
    # 가드레일 G5: 로컬 시연 전용으로 127.0.0.1에만 바인딩
    uvicorn.run(app, host=server["host"], port=server["port"])
