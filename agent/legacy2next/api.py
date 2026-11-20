"""FastAPI 앱: /query 단일 진입점, 실행 조회·승인·중단, SSE."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from . import __version__
from .config import AgentConfig, load_config
from .events import EventLog, RunEvent
from .runs import RunError, RunService
from .schemas import (
    AnalysisDecision,
    DesignDecision,
    LogLine,
    QueryRequest,
    QueryResponse,
    RunDetail,
    SiteSummary,
)

SSE_PING_SECONDS = 15


class HealthResponse(BaseModel):
    status: str
    version: str
    llm_calls_per_run: int


def _service(request: Request) -> RunService:
    return request.app.state.runs


def _bad_request(e: RunError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(e))


def _run_event_payload(event: RunEvent) -> list[str]:
    """에이전트 이벤트 → 콘솔 SSE 메시지 (ui/src/api/types.ts RunEvent)."""
    messages: list[str] = []
    if event.type in ("log", "guardrail"):
        source = "guard" if event.type == "guardrail" else event.source
        line = LogLine(at=event.at, source=source, level=event.level, message=event.message)
        messages.append(
            json.dumps({"type": "log", "line": line.model_dump(by_alias=True)}, ensure_ascii=False)
        )
    if event.type != "log":
        messages.append(json.dumps({"type": "changed"}))
    return messages


def create_app(config: AgentConfig | None = None) -> FastAPI:
    cfg = config or load_config()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        checkpoint = cfg.resolved_checkpoint_path()
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        async with AsyncSqliteSaver.from_conn_string(str(checkpoint)) as saver:
            events = EventLog(cfg.resolved_log_dir())
            runs = RunService(cfg, events, saver, cfg.stub_step_ms / 1000)
            runs.mark_interrupted_runs()
            app.state.events = events
            app.state.runs = runs
            yield

    app = FastAPI(title="Legacy2Next Agent", version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok", version=__version__, llm_calls_per_run=cfg.limits.llm_calls_per_run
        )

    @app.post("/query", response_model_by_alias=True)
    async def query(body: QueryRequest, request: Request) -> QueryResponse:
        """단일 진입점. url이 있으면 생성 요청, question이 있으면 질의 (Router 분류는 T05)."""
        runs = _service(request)
        try:
            if body.url:
                kind = body.kind or "new"
                runs.start(body.alias, body.url, kind)
                return QueryResponse(intent=kind, run=await runs.snapshot(body.alias))
            if body.question:
                return QueryResponse(intent="query", answer=runs.answer(body.alias, body.question))
        except RunError as e:
            raise _bad_request(e) from e
        raise HTTPException(status_code=400, detail="url 또는 question 중 하나가 필요합니다.")

    @app.get("/runs", response_model_by_alias=True)
    def list_runs(request: Request) -> list[SiteSummary]:
        return _service(request).list_sites()

    @app.get("/runs/{alias}", response_model_by_alias=True)
    async def get_run(alias: str, request: Request) -> RunDetail:
        try:
            return await _service(request).snapshot(alias)
        except RunError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

    @app.post("/runs/{alias}/analysis", status_code=202)
    async def submit_analysis(
        alias: str, body: AnalysisDecision, request: Request
    ) -> dict[str, str]:
        try:
            await _service(request).submit_analysis(alias, body)
        except RunError as e:
            raise _bad_request(e) from e
        return {"status": "accepted"}

    @app.post("/runs/{alias}/design", status_code=202)
    async def submit_design(alias: str, body: DesignDecision, request: Request) -> dict[str, str]:
        try:
            await _service(request).submit_design(alias, body)
        except RunError as e:
            raise _bad_request(e) from e
        return {"status": "accepted"}

    @app.post("/runs/{alias}/stop", status_code=202)
    async def stop_run(alias: str, request: Request) -> dict[str, str]:
        try:
            _service(request).stop(alias)
        except RunError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        return {"status": "accepted"}

    @app.get("/runs/{alias}/events")
    async def run_events(alias: str, request: Request) -> EventSourceResponse:
        events: EventLog = request.app.state.events
        queue, unsubscribe = events.queue(alias)

        async def stream() -> AsyncIterator[ServerSentEvent]:
            try:
                while True:
                    event = await queue.get()
                    for data in _run_event_payload(event):
                        yield ServerSentEvent(data=data)
            finally:
                unsubscribe()

        return EventSourceResponse(stream(), ping=SSE_PING_SECONDS)

    @app.get("/events")
    async def site_events(request: Request) -> EventSourceResponse:
        """사이트 목록이 바뀔 수 있는 이벤트(상태 변화)만 알린다."""
        events: EventLog = request.app.state.events
        queue: asyncio.Queue[RunEvent] = asyncio.Queue()
        unsubscribe = events.subscribe_all(
            lambda e: queue.put_nowait(e) if e.type == "status" else None
        )

        async def stream() -> AsyncIterator[ServerSentEvent]:
            try:
                while True:
                    event = await queue.get()
                    yield ServerSentEvent(
                        data=json.dumps({"type": "changed", "alias": event.run_id})
                    )
            finally:
                unsubscribe()

        return EventSourceResponse(stream(), ping=SSE_PING_SECONDS)

    return app
