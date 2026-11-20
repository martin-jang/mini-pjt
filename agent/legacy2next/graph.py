"""LangGraph 고정 그래프 (T04: 노드는 스텁).

Router → ① Explorer → ② Analyst → ⏸ 분석 리뷰 → ③ Designer → ⏸ 디자인 확인 → ④ Builder → ⑤ Verifier
승인 2곳은 interrupt()로 멈추고, 콘솔의 결정으로 Command(resume=...) 재개한다.
interrupt()가 있는 노드는 재개 때 처음부터 다시 실행되므로, 대기 이벤트는 앞 노드에서 남긴다.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, interrupt

from . import stubs
from .browser import GuardedBrowser, McpBrowser
from .config import AgentConfig
from .events import EventLog, EventType, RunEvent
from .explorer import explore_links
from .schemas import (
    AnalysisDecision,
    AnalysisReview,
    ApprovedAnalysis,
    DesignChange,
    DesignDecision,
    DesignReview,
    RunStatus,
    StageId,
    StageState,
)

STUB = "(스텁) "


class GraphState(TypedDict, total=False):
    run_id: str
    alias: str
    url: str
    kind: Literal["new", "extend"]
    intent: str
    analysis: dict[str, Any]
    approved_analysis: dict[str, Any]
    design: dict[str, Any]
    result: dict[str, Any]


@dataclass
class Emitter:
    """노드가 실행 이벤트를 남기는 도우미."""

    events: EventLog
    run_id: str
    step_delay: float

    def _emit(
        self, type_: EventType, source: str, message: str, level: str = "info", **data: Any
    ) -> None:
        self.events.emit(
            RunEvent(
                run_id=self.run_id,
                type=type_,
                source=source,
                message=message,
                level=level,
                data=data,
            )  # type: ignore[arg-type]
        )

    def log(self, source: str, message: str, level: str = "info") -> None:
        self._emit("log", source, message, level)

    def stage(self, stage: StageId, state: StageState, note: str | None = None) -> None:
        self._emit("stage", "system", f"{stage} {state}", stage=stage, state=state, note=note)

    def status(self, status: RunStatus, **data: Any) -> None:
        self._emit("status", "system", status, status=status, **data)

    def guardrail(self, rule: str, detail: str, outcome: str, message: str) -> None:
        level = "block" if outcome == "blocked" else "warn"
        self._emit("guardrail", "guard", message, level, rule=rule, detail=detail, outcome=outcome)

    def metrics(self, **values: int) -> None:
        self._emit("metrics", "system", "metrics", **values)

    async def step(self) -> None:
        """스텁 진행 속도 (콘솔에서 단계가 흐르는 모습을 보이기 위함)."""
        if self.step_delay > 0:
            await asyncio.sleep(self.step_delay)


@dataclass
class GraphDeps:
    events: EventLog
    config: AgentConfig = field(default_factory=AgentConfig)

    @property
    def step_delay(self) -> float:
        return self.config.stub_step_ms / 1000

    def emitter(self, state: GraphState) -> Emitter:
        return Emitter(self.events, state["run_id"], self.step_delay)


def build_graph(deps: GraphDeps, checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    async def router(state: GraphState) -> dict[str, Any]:
        em = deps.emitter(state)
        intent = state.get("kind", "new")
        em.log(
            "router",
            f"의도: {'신규 생성' if intent == 'new' else '확장'} (새 요청 폼, Router LLM 생략)",
        )
        await em.step()
        return {"intent": intent}

    async def explorer(state: GraphState) -> dict[str, Any]:
        em = deps.emitter(state)
        em.stage("explorer", "running")
        if deps.config.explorer.mode == "stub":
            em.log("explorer", f"{STUB}대상 {state['url']} — 브라우저 없이 예시 화면을 씁니다")
            await em.step()
            em.metrics(screens_collected=stubs.TOTAL_COLLECTED_SCREENS)
            em.stage("explorer", "done", f"{stubs.TOTAL_COLLECTED_SCREENS}개 화면")
            return {}

        cfg = deps.config
        origins = cfg.allowed_origins(state["alias"], state["url"])
        em.log("explorer", f"허용 origin: {', '.join(origins)}")

        def guard(rule: str, detail: str, outcome: str, message: str) -> None:
            em.guardrail(rule, detail, outcome, message)

        output_dir = cfg.site_dir(state["alias"]) / "crawl" / "_mcp"
        async with McpBrowser(origins, output_dir, headless=cfg.explorer.headless) as mcp:
            em.log("explorer", "Playwright MCP 브라우저 시작")
            browser = GuardedBrowser(mcp, origins, guard)
            report = await explore_links(
                browser, state["url"], cfg.explorer.max_links, lambda m: em.log("explorer", m)
            )
            await browser.call("browser_close", {})
        em.metrics(screens_collected=len(report.pages))
        em.log(
            "explorer",
            f"확인한 화면 {len(report.pages)}개, 차단 {len(report.blocked)}건, "
            f"건너뜀 {len(report.skipped)}건 (사이트맵 수집은 T07c)",
        )
        em.stage("explorer", "done", f"{len(report.pages)}개 화면")
        return {}

    async def analyst(state: GraphState) -> dict[str, Any]:
        em = deps.emitter(state)
        em.stage("analyst", "running")
        for message in [
            "사이트 성격 추론",
            "화면 목록 정리",
            "변이 후보 정리",
            "Happy Path 후보와 데이터 연결 방식 제안",
        ]:
            em.log("analyst", STUB + message)
            await em.step()
        em.stage("analyst", "done")
        return {"analysis": stubs.build_analysis().model_dump()}

    # 대기 알림은 별도 게이트 노드에서 남긴다. 앞 노드의 상태가 저장된 뒤라 콘솔이 바로 읽을 수 있고
    # interrupt 노드는 재개 때 처음부터 다시 실행되므로 거기서 알리면 중복된다
    async def analysis_gate(state: GraphState) -> dict[str, Any]:
        em = deps.emitter(state)
        em.stage("analysisReview", "waiting")
        em.status("awaiting_analysis")
        em.log("gate", "승인 1 대기: 분석 리뷰")
        return {}

    async def design_gate(state: GraphState) -> dict[str, Any]:
        em = deps.emitter(state)
        em.stage("designReview", "waiting")
        em.status("awaiting_design")
        return {}

    async def finish(state: GraphState) -> dict[str, Any]:
        em = deps.emitter(state)
        em.status("done")
        em.log("system", f"완료: next-pjt/{state['alias']}/ (스텁 결과)")
        return {}

    async def analysis_review(state: GraphState) -> Command[str]:
        raw = interrupt({"gate": "analysis"})
        decision = AnalysisDecision.model_validate(raw)
        em = deps.emitter(state)
        comment = f": {decision.comment}" if decision.comment else ""
        if decision.action == "reject":
            em.stage("analysisReview", "stopped")
            em.log("gate", f"분석 리뷰 반려{comment}", "warn")
            em.status("stopped")
            return Command(goto=END)
        if decision.action == "revise":
            em.log("gate", f"분석 수정 요청{comment}")
            em.log("analyst", f"{STUB}수정 요청을 받았습니다. 실제 반영은 T10~T11에서 붙습니다")
            return Command(goto="analysis_gate")
        analysis = AnalysisReview.model_validate(state["analysis"])
        approved = ApprovedAnalysis.model_validate(decision.model_dump())
        screens = stubs.build_design_screens(analysis, approved.happy_path_ids)
        design = DesignReview(design_system=f"{state['alias']} 디자인 시스템", screens=screens)
        em.stage("analysisReview", "done")
        em.status("running")
        em.log("gate", "승인 1 완료: 분석 리뷰")
        return Command(
            goto="designer",
            update={"approved_analysis": approved.model_dump(), "design": design.model_dump()},
        )

    async def designer(state: GraphState) -> dict[str, Any]:
        em = deps.emitter(state)
        design = DesignReview.model_validate(state["design"])
        em.stage("designer", "running")
        em.log("designer", f"{STUB}디자인 시스템 생성 — 실제 Stitch 연동은 T12에서 붙습니다")
        await em.step()
        total = len(design.screens)
        for i, screen in enumerate(design.screens, start=1):
            em.log("designer", f"{STUB}화면 디자인 {i}/{total}: {screen.path}")
            em.stage("designer", "running", f"화면 {total}개 중 {i}개")
            await em.step()
        em.stage("designer", "done", f"화면 {total}개")
        em.log("gate", "승인 2 대기: 디자인 확인")
        return {}

    async def design_review(state: GraphState) -> Command[str]:
        raw = interrupt({"gate": "design"})
        decision = DesignDecision.model_validate(raw)
        em = deps.emitter(state)
        design = DesignReview.model_validate(state["design"])
        by_id = {s.id: s for s in design.screens}

        if decision.action == "rejectAll":
            comment = f": {decision.comment}" if decision.comment else ""
            em.stage("designReview", "stopped")
            em.log("gate", f"디자인 전체 반려{comment}", "warn")
            em.status("stopped")
            return Command(goto=END)
        if decision.action == "approveScreen" and decision.screen_id in by_id:
            screen = by_id[decision.screen_id]
            screen.state = "approved"
            em.log("gate", f"화면 승인: {screen.path}")
        elif decision.action == "approveRegular":
            regular = [s for s in design.screens if not s.major_change and s.state == "pending"]
            for s in regular:
                s.state = "approved"
            em.log("gate", f"일반 화면 {len(regular)}개 일괄 승인")
        elif decision.action == "revise" and decision.screen_id in by_id:
            screen = by_id[decision.screen_id]
            em.log("gate", f"화면 수정 요청: {screen.path} — {decision.comment}")
            screen.changes.append(
                DesignChange(what=f"수정 요청 반영: {decision.comment}", why="사용자 수정 요청")
            )
            screen.state = "pending"
            em.log("designer", f"{STUB}수정 요청 반영: {screen.path}")

        if all(s.state == "approved" for s in design.screens):
            em.stage("designReview", "done")
            em.status("running")
            em.log("gate", "승인 2 완료: 디자인 확인")
            return Command(goto="builder", update={"design": design.model_dump()})
        return Command(goto="design_gate", update={"design": design.model_dump()})

    async def builder(state: GraphState) -> dict[str, Any]:
        em = deps.emitter(state)
        design = DesignReview.model_validate(state["design"])
        em.stage("builder", "running")
        em.log("builder", f"{STUB}공통 컴포넌트 생성 — 실제 코드 생성은 T13~T14에서 붙습니다")
        await em.step()
        for screen in design.screens:
            em.log("builder", f"{STUB}화면 생성: {screen.path}")
            await em.step()
        em.stage("builder", "done", f"화면 {len(design.screens)}개")
        return {}

    async def verifier(state: GraphState) -> dict[str, Any]:
        em = deps.emitter(state)
        em.stage("verifier", "running")
        for message in ["빌드", "Happy Path 흐름 테스트", "기능 보존 대조", "계정 원문 검색"]:
            em.log("verifier", f"{STUB}{message} — 실제 검증은 T15에서 붙습니다")
            await em.step()
        result = stubs.build_result(
            state["alias"],
            AnalysisReview.model_validate(state["analysis"]),
            ApprovedAnalysis.model_validate(state["approved_analysis"]),
            DesignReview.model_validate(state["design"]).screens,
        )
        em.stage("verifier", "done")
        return {"result": result.model_dump()}

    graph = StateGraph(GraphState)
    graph.add_node("router", router)
    graph.add_node("explorer", explorer)
    graph.add_node("analyst", analyst)
    graph.add_node("analysis_gate", analysis_gate)
    graph.add_node(
        "analysis_review", analysis_review, destinations=("designer", "analysis_gate", END)
    )
    graph.add_node("designer", designer)
    graph.add_node("design_gate", design_gate)
    graph.add_node("design_review", design_review, destinations=("builder", "design_gate", END))
    graph.add_node("builder", builder)
    graph.add_node("verifier", verifier)
    graph.add_node("finish", finish)
    graph.add_edge(START, "router")
    graph.add_edge("router", "explorer")
    graph.add_edge("explorer", "analyst")
    graph.add_edge("analyst", "analysis_gate")
    graph.add_edge("analysis_gate", "analysis_review")
    graph.add_edge("designer", "design_gate")
    graph.add_edge("design_gate", "design_review")
    graph.add_edge("builder", "verifier")
    graph.add_edge("verifier", "finish")
    graph.add_edge("finish", END)
    return graph.compile(checkpointer=checkpointer)
