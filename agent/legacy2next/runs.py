"""실행 관리: 그래프 시작·재개·중단, 콘솔에 보낼 실행 스냅샷 만들기.

스냅샷 = 이벤트 로그를 접은 것(단계·로그·가드레일·시간·지표) + 그래프 상태(분석·디자인·결과).
실행 ID는 사이트 별칭을 그대로 쓴다 (그래프 thread_id도 같다).
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections import Counter
from datetime import datetime
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Command
from pydantic import ValidationError

from .config import AgentConfig, origin_of
from .crawl import CrawlStore, MenuItem
from .events import EventLog, RunEvent
from .graph import GraphDeps, build_graph
from .llm import LlmGateway
from .login import AuthHandoffs
from .schemas import (
    STAGE_ORDER,
    AnalysisDecision,
    AuthDecision,
    AuthRequest,
    DesignDecision,
    DesignReview,
    GuardrailEvent,
    LogLine,
    QueryAnswer,
    RunDetail,
    RunKind,
    RunMetrics,
    RunStatus,
    RunTiming,
    SiteMapLink,
    SiteMapMenuItem,
    SiteMapScreen,
    SiteMapView,
    SiteSummary,
    StageInfo,
)

logger = logging.getLogger(__name__)

ALIAS_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,31}$")
ACTIVE: set[str] = {"running", "awaiting_auth", "awaiting_analysis", "awaiting_design"}
WAITING: set[str] = {"awaiting_auth", "awaiting_analysis", "awaiting_design"}
FINAL: set[str] = {"done", "stopped", "failed"}
PREVIOUS_TASK_WAIT_SECONDS = 5
# 콘솔에 보여 줄 '따라가지 않은 링크' 수 상한
NOT_FOLLOWED_LIMIT = 40


class RunError(ValueError):
    """요청을 받아들일 수 없음. 메시지는 콘솔에 그대로 보여준다."""


def _ms_between(start: str, end: str) -> int:
    return int((datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() * 1000)


def _format_duration(ms: int) -> str:
    sec = max(0, round(ms / 1000))
    return f"{sec // 60}분 {sec % 60}초" if sec >= 60 else f"{sec}초"


def fold_events(alias: str, events: list[RunEvent], llm_limit: int) -> RunDetail:
    """이벤트 목록을 실행 스냅샷(그래프 상태 제외)으로 접는다."""
    if not events:
        raise RunError(f"'{alias}' 실행을 찾을 수 없습니다.")
    stages = {sid: StageInfo(id=sid) for sid in STAGE_ORDER}
    stage_started: dict[str, str] = {}
    logs: list[LogLine] = []
    guardrails: list[GuardrailEvent] = []
    metrics = RunMetrics(llm_limit=llm_limit)
    timing = RunTiming(started_at=events[0].at)
    status: RunStatus = "running"
    url, kind = "", "new"
    auth: AuthRequest | None = None

    for e in events:
        d = e.data
        if e.type == "status":
            new_status = d.get("status", status)
            url = d.get("url", url)
            kind = d.get("kind", kind)
            auth = (
                AuthRequest.model_validate(d["auth"])
                if new_status == "awaiting_auth" and d.get("auth")
                else None
            )
            if status in WAITING and new_status not in WAITING and timing.waiting_since:
                timing.wait_ms += _ms_between(timing.waiting_since, e.at)
                timing.waiting_since = None
            if new_status in WAITING and status not in WAITING:
                timing.waiting_since = e.at
            if new_status in FINAL:
                timing.finished_at = e.at
            status = new_status
        elif e.type == "stage":
            stage = stages[d["stage"]]
            stage.state = d["state"]
            if d["state"] == "running" and d["stage"] not in stage_started:
                stage_started[d["stage"]] = e.at
            note = d.get("note")
            if d["state"] == "done" and d["stage"] in stage_started:
                took = _format_duration(_ms_between(stage_started[d["stage"]], e.at))
                note = f"{note} · {took}" if note else took
            if note:
                stage.note = note
        elif e.type == "metrics":
            metrics.screens_collected = d.get("screens_collected", metrics.screens_collected)
        elif e.type == "llm":
            metrics.llm_calls += 1
        elif e.type == "guardrail":
            guardrails.insert(
                0,
                GuardrailEvent(
                    at=e.at,
                    rule=d.get("rule", "?"),
                    detail=d.get("detail", e.message),
                    outcome=d.get("outcome", "blocked"),
                ),
            )
            logs.append(LogLine(at=e.at, source="guard", level=e.level, message=e.message))
        elif e.type == "log":
            logs.append(LogLine(at=e.at, source=e.source, level=e.level, message=e.message))

    if status in FINAL:
        for stage in stages.values():
            if stage.state in ("running", "waiting"):
                stage.state = "stopped"
    return RunDetail(
        alias=alias,
        url=url,
        status=status,
        kind=kind,  # type: ignore[arg-type]
        stages=list(stages.values()),
        metrics=metrics,
        timing=timing,
        logs=logs,
        guardrails=guardrails,
        auth=auth,
    )


class RunService:
    def __init__(
        self,
        config: AgentConfig,
        events: EventLog,
        checkpointer: BaseCheckpointSaver,
        llm: LlmGateway | None = None,
    ) -> None:
        self._config = config
        self._events = events
        self._auth = AuthHandoffs()
        self._graph = build_graph(GraphDeps(events, config, llm, self._auth), checkpointer)
        self._tasks: dict[str, asyncio.Task[None]] = {}

    @staticmethod
    def _thread(alias: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": alias}}

    def _emit_status(
        self, alias: str, status: RunStatus, message: str, level: str = "info", **data: Any
    ) -> None:
        self._events.emit(
            RunEvent(run_id=alias, type="log", source="system", message=message, level=level)
        )  # type: ignore[arg-type]
        self._events.emit(
            RunEvent(
                run_id=alias,
                type="status",
                source="system",
                message=status,
                data={"status": status, **data},
            )
        )

    def _status(self, alias: str) -> RunStatus | None:
        events = self._events.read(alias)
        if not events:
            return None
        return fold_events(alias, events, self._config.limits.llm_calls_per_run).status

    def _launch(self, alias: str, payload: Any) -> None:
        async def run() -> None:
            try:
                # 단계마다 저장을 마친 뒤 다음 단계로 간다. 기본(async)이면 다음 노드가 보내는
                # 상태 알림이 앞 노드 결과 저장보다 먼저 나가 콘솔이 빈 데이터를 읽을 수 있다
                await self._graph.ainvoke(payload, self._thread(alias), durability="sync")
            except asyncio.CancelledError:
                raise
            except Exception as e:  # 노드 오류는 실행 실패로 기록하고 서버는 계속 돈다
                logger.exception("실행 실패: %s", alias)
                self._emit_status(alias, "failed", f"실행 실패: {e}", "block")
            finally:
                self._tasks.pop(alias, None)

        self._tasks[alias] = asyncio.create_task(run(), name=f"run:{alias}")

    async def wait_idle(self, alias: str) -> None:
        """테스트용: 실행 중인 그래프 작업이 끝날 때까지 기다린다."""
        task = self._tasks.get(alias)
        if task:
            await asyncio.wait({task})

    # ── 요청 ─────────────────────────────

    def start(self, alias: str, url: str, kind: RunKind) -> None:
        if not ALIAS_PATTERN.match(alias):
            raise RunError("별칭은 영문 소문자·숫자·하이픈으로 2~32자여야 합니다.")
        try:
            origin_of(url)
        except ValueError as e:
            raise RunError("http:// 또는 https://로 시작하는 URL을 입력하세요.") from e
        if kind == "extend":
            raise RunError("확장 요청은 T16에서 지원합니다. 지금은 신규 생성만 됩니다.")
        if self._events.read(alias):
            raise RunError(f"'{alias}' 별칭이 이미 있습니다. 다른 별칭을 쓰세요.")
        self._emit_status(alias, "running", f"실행 시작: {url}", url=url, kind=kind)
        self._launch(alias, {"run_id": alias, "alias": alias, "url": url, "kind": kind})

    async def _require_waiting(self, alias: str, expected: RunStatus, label: str) -> None:
        task = self._tasks.get(alias)
        if task:
            # 바로 앞 요청(게이트까지 짧게 도는 작업)이 끝나기를 잠깐 기다린다
            done, _ = await asyncio.wait({task}, timeout=PREVIOUS_TASK_WAIT_SECONDS)
            if not done:
                raise RunError("이전 요청을 처리하는 중입니다. 잠시 후 다시 시도하세요.")
        if self._status(alias) != expected:
            raise RunError(f"{label} 승인 대기 상태가 아닙니다.")

    async def submit_analysis(self, alias: str, decision: AnalysisDecision) -> None:
        await self._require_waiting(alias, "awaiting_analysis", "분석 리뷰")
        if decision.action == "approve" and not decision.happy_path_ids:
            raise RunError("Happy Path를 하나 이상 고르세요.")
        if decision.action == "revise" and not (decision.comment or "").strip():
            raise RunError("수정 요청 내용을 입력하세요.")
        self._launch(alias, Command(resume=decision.model_dump()))

    async def submit_design(self, alias: str, decision: DesignDecision) -> None:
        await self._require_waiting(alias, "awaiting_design", "디자인 확인")
        if decision.action in ("approveScreen", "revise"):
            state = await self._graph.aget_state(self._thread(alias))
            design = DesignReview.model_validate(state.values["design"])
            screen = next((s for s in design.screens if s.id == decision.screen_id), None)
            if screen is None:
                raise RunError("화면을 찾을 수 없습니다.")
            if not screen.major_change:
                raise RunError("일반 변경 화면은 자동 승인됩니다. 대폭 변경 화면만 확인하세요.")
        if decision.action == "revise" and not (decision.comment or "").strip():
            raise RunError("수정 요청 내용을 입력하세요.")
        self._launch(alias, Command(resume=decision.model_dump()))

    async def submit_auth(self, alias: str, decision: AuthDecision) -> None:
        await self._require_waiting(alias, "awaiting_auth", "사용자 인증")
        self._launch(alias, Command(resume=decision.model_dump()))

    async def stop(self, alias: str) -> None:
        status = self._status(alias)
        if status is None:
            raise RunError(f"'{alias}' 실행을 찾을 수 없습니다.")
        if status not in ACTIVE:
            return
        task = self._tasks.pop(alias, None)
        if task:
            task.cancel()
        await self._auth.close(alias)
        self._emit_status(alias, "stopped", "사용자가 실행을 중단했습니다", "warn")

    def delete_session(self, alias: str) -> bool:
        """저장한 로그인 세션 파일을 지운다 (G10). 지웠으면 True."""
        status = self._status(alias)
        if status is None:
            raise RunError(f"'{alias}' 실행을 찾을 수 없습니다.")
        if status in ("running", "awaiting_auth"):
            raise RunError("수집 중에는 로그인 세션을 지울 수 없습니다. 실행을 멈춘 뒤 지우세요.")
        path = self._config.session_path(alias)
        if not path.exists():
            return False
        path.unlink()
        self._events.emit(
            RunEvent(
                run_id=alias, type="log", source="system", message="로그인 세션 파일을 삭제했습니다"
            )
        )
        return True

    async def aclose(self) -> None:
        """서버 종료: 열려 있는 사용자 인증 브라우저를 닫는다."""
        await self._auth.close_all()

    def mark_interrupted_runs(self) -> None:
        """서버 재시작으로 끊긴 진행 중 실행을 실패로 표시한다 (승인 대기는 그대로 재개 가능)."""
        for alias in self._events.run_ids():
            if self._status(alias) == "running" and alias not in self._tasks:
                self._emit_status(
                    alias, "failed", "서버가 다시 시작되어 진행 중이던 실행이 끊겼습니다", "warn"
                )

    # ── 조회 ─────────────────────────────

    def list_sites(self) -> list[SiteSummary]:
        sites: list[SiteSummary] = []
        for alias in self._events.run_ids():
            events = self._events.read(alias)
            if events:
                d = fold_events(alias, events, self._config.limits.llm_calls_per_run)
                sites.append(SiteSummary(alias=d.alias, url=d.url, status=d.status))
        return sites

    async def snapshot(self, alias: str) -> RunDetail:
        if not ALIAS_PATTERN.match(alias):
            raise RunError(f"'{alias}' 실행을 찾을 수 없습니다.")
        detail = fold_events(alias, self._events.read(alias), self._config.limits.llm_calls_per_run)
        values = (await self._graph.aget_state(self._thread(alias))).values
        try:
            update: dict[str, Any] = {
                key: values[key]
                for key in ("analysis", "approved_analysis", "design", "result")
                if values.get(key)
            }
            update["session_saved"] = self._config.session_path(alias).exists()
            sitemap = self._sitemap(alias)
            if sitemap:
                update["sitemap"] = sitemap
            return detail.model_validate({**detail.model_dump(), **update})
        except ValidationError:
            logger.exception("그래프 상태를 읽지 못했습니다: %s", alias)
            return detail

    def _sitemap(self, alias: str) -> SiteMapView | None:
        """crawl/graph.json을 콘솔용 요약으로 바꾼다. 없거나 읽지 못하면 None."""
        try:
            graph = CrawlStore(self._config.site_dir(alias) / "crawl").load_graph()
        except OSError, ValidationError:
            logger.exception("사이트맵을 읽지 못했습니다: %s", alias)
            return None
        if graph is None:
            return None
        inbound = Counter(
            e.target for e in graph.edges if e.target and e.status in ("followed", "duplicate")
        )

        def menu(items: list[MenuItem]) -> list[SiteMapMenuItem]:
            return [
                SiteMapMenuItem(label=i.label, screen_id=i.screen_id, children=menu(i.children))
                for i in items
            ]

        not_followed: dict[tuple[str, str], SiteMapLink] = {}
        for e in graph.edges:
            if e.status in ("blocked", "skipped", "limit", "failed"):
                key = (e.label, e.status)
                if key not in not_followed and len(not_followed) < NOT_FOLLOWED_LIMIT:
                    not_followed[key] = SiteMapLink(
                        label=e.label, url=e.url, status=e.status, reason=e.reason
                    )
        return SiteMapView(
            screens=[
                SiteMapScreen(
                    screen_id=n.screen_id,
                    title=n.title,
                    url=n.url,
                    depth=n.depth,
                    tables=n.tables,
                    forms=n.forms,
                    buttons=n.buttons,
                    inbound=inbound[n.screen_id],
                )
                for n in graph.nodes
            ],
            menu=menu(graph.menu),
            edge_counts=dict(Counter(e.status for e in graph.edges)),
            not_followed=list(not_followed.values()),
            truncated=graph.truncated,
        )

    def answer(self, alias: str, question: str) -> QueryAnswer:
        """질의 스텁. 실제 답변(Chroma 검색)은 T17, 범위 밖 거절(Router)은 T05에서 붙는다."""
        if not self._events.read(alias):
            return QueryAnswer(kind="rejected", text=f"'{alias}'는 분석한 적이 없는 사이트입니다.")
        return QueryAnswer(
            kind="answer",
            text=f"(스텁) '{question}' 질문을 받았습니다. 질의 응답은 T17에서 붙습니다.",
        )
