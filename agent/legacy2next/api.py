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
from .config import AgentConfig, Secrets, load_config
from .events import EventLog, RunEvent
from .fake_llm import FakeLlmClient
from .llm import (
    CallBudget,
    LlmBudgetExceededError,
    LlmGateway,
    LlmRefusalError,
    MessagesClient,
    create_bedrock_client,
)
from .router import REJECT_TEXT, Router
from .runs import RunError, RunService
from .schemas import (
    AnalysisDecision,
    AuthDecision,
    DesignDecision,
    LogLine,
    QueryAnswer,
    QueryRequest,
    QueryResponse,
    RunDetail,
    SiteSummary,
    StartSuggestion,
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


def create_app(
    config: AgentConfig | None = None,
    *,
    llm_client: MessagesClient | None = None,
    fake_llm: bool = False,
) -> FastAPI:
    """llm_client가 있으면 그것을, fake_llm이면 테스트용 가짜 LLM을, 둘 다 없으면 Bedrock을 쓴다."""
    cfg = config or load_config()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        checkpoint = cfg.resolved_checkpoint_path()
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        async with AsyncSqliteSaver.from_conn_string(str(checkpoint)) as saver:
            events = EventLog(cfg.resolved_log_dir())
            settings = Secrets()
            client = llm_client or (
                FakeLlmClient() if fake_llm else create_bedrock_client(settings)
            )
            # 실행 노드용 LLM: 실행(별칭)마다 호출 수를 센다 (G8)
            run_llm = LlmGateway(
                client,
                settings.bedrock_model_id,
                CallBudget(cfg.limits.llm_calls_per_run),
                events,
            )
            runs = RunService(cfg, events, saver, run_llm)
            runs.mark_interrupted_runs()
            router_events = EventLog(cfg.resolved_log_dir() / "router")
            gateway = LlmGateway(
                client,
                settings.bedrock_model_id,
                CallBudget(cfg.limits.router_calls),
                router_events,
            )
            app.state.router = Router(gateway, router_events)
            app.state.events = events
            app.state.runs = runs
            try:
                yield
            finally:
                await runs.aclose()

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
        """단일 진입점. url이 있으면 새 요청 폼(의도가 정해짐), question이면 Router가 분류한다."""
        runs = _service(request)
        if body.url:
            kind = body.kind or "new"
            try:
                runs.start(body.alias or "", body.url, kind)
                return QueryResponse(intent=kind, run=await runs.snapshot(body.alias or ""))
            except RunError as e:
                raise _bad_request(e) from e
        if not (body.question or "").strip():
            raise HTTPException(status_code=400, detail="url 또는 question 중 하나가 필요합니다.")

        router: Router = request.app.state.router
        sites = runs.list_sites()
        rejected = QueryResponse(
            intent="out_of_scope", answer=QueryAnswer(kind="rejected", text=REJECT_TEXT)
        )
        try:
            decision = await router.classify(
                body.question or "", [s.alias for s in sites], body.alias
            )
        except LlmBudgetExceededError as e:
            raise HTTPException(status_code=429, detail=str(e)) from e
        except LlmRefusalError:
            return rejected
        except Exception as e:  # LLM 연결·인증 오류는 콘솔에 원인을 알린다
            raise HTTPException(
                status_code=503, detail=f"Router LLM 호출에 실패했습니다 ({type(e).__name__})."
            ) from e

        if decision.intent == "out_of_scope":
            return rejected
        if decision.intent == "query":
            if not decision.alias:
                text = "어느 사이트에 대한 질문인지 대상 사이트를 골라 주세요."
                return QueryResponse(intent="query", answer=QueryAnswer(kind="answer", text=text))
            answer = runs.answer(decision.alias, body.question or "")
            return QueryResponse(intent="query", answer=answer)
        if decision.intent == "new" and not decision.url:
            text = "분석할 레거시 사이트의 URL(http:// 또는 https://)을 함께 알려 주세요."
            return QueryResponse(intent="new", answer=QueryAnswer(kind="answer", text=text))
        site_url = decision.url or next((s.url for s in sites if s.alias == decision.alias), None)
        label = "새 POC 생성" if decision.intent == "new" else "기존 결과물 확장"
        return QueryResponse(
            intent=decision.intent,
            answer=QueryAnswer(
                kind="start",
                text=f"{label} 요청으로 이해했습니다. 새 요청 화면에서 값을 확인하고 시작하세요.",
                start=StartSuggestion(kind=decision.intent, url=site_url, alias=decision.alias),
            ),
        )

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

    @app.post("/runs/{alias}/auth", status_code=202)
    async def submit_auth(alias: str, body: AuthDecision, request: Request) -> dict[str, str]:
        """사용자가 브라우저에서 인증을 마쳤음(done) 또는 취소(cancel)."""
        try:
            await _service(request).submit_auth(alias, body)
        except RunError as e:
            raise _bad_request(e) from e
        return {"status": "accepted"}

    @app.post("/runs/{alias}/session/delete")
    async def delete_session(alias: str, request: Request) -> dict[str, bool]:
        """저장한 로그인 세션 파일 삭제 (G10)."""
        try:
            deleted = _service(request).delete_session(alias)
        except RunError as e:
            raise _bad_request(e) from e
        return {"deleted": deleted}

    @app.post("/runs/{alias}/stop", status_code=202)
    async def stop_run(alias: str, request: Request) -> dict[str, str]:
        try:
            await _service(request).stop(alias)
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
