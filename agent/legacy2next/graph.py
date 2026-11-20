"""LangGraph 고정 그래프 (T04: 노드는 스텁).

Router → ① 로그인(⏸ 사용자 인증) → Explorer → ② Analyst → ⏸ 분석 리뷰 → ③ Designer
→ ⏸ 디자인 확인 → ④ Builder → ⑤ Verifier
승인 2곳과 사용자 인증 넘김은 interrupt()로 멈추고, 콘솔의 결정으로 Command(resume=...) 재개한다.
interrupt()가 있는 노드는 재개 때 처음부터 다시 실행되므로, 대기 이벤트는 앞 노드에서 남긴다.
"""

from __future__ import annotations

import asyncio
import shutil
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, interrupt

from . import stubs
from .browser import BrowserActionError, GuardedBrowser, McpBrowser, ToolResult
from .capture import capture_screen
from .config import AgentConfig, load_site_credentials
from .crawl import (
    CrawlStore,
    FlowStep,
    ScreenCapture,
    SiteGraph,
    UseCaseCandidate,
    screen_id_for,
)
from .events import EventLog, EventType, RunEvent
from .explorer import (
    ExplorerError,
    MapLimits,
    ScreenResult,
    SessionExpiredError,
    map_site,
)
from .llm import LlmGateway
from .login import (
    AuthHandoffs,
    LoginDetector,
    check_login,
    register_session_secrets,
    secrets_file,
    staging_dir,
)
from .masking import secrets
from .schemas import (
    AnalysisDecision,
    AnalysisReview,
    ApprovedAnalysis,
    AuthDecision,
    AuthRequest,
    DesignChange,
    DesignDecision,
    DesignReview,
    RunStatus,
    StageId,
    StageState,
)
from .walker import WalkDecider, WalkDecision, WalkLimits, hypothesize, run_walk

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
    # 사용자 인증 넘김 요청 (없으면 None)
    auth: dict[str, Any] | None
    # 로그인 화면 주소 (수집 중 여기로 되돌아가면 세션 만료)
    login_url: str | None
    login_attempts: int


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
    # 실행 노드가 쓰는 LLM (실행당 호출 수 한도 G8). 스텁 수집에서는 없어도 된다
    llm: LlmGateway | None = None
    auth: AuthHandoffs = field(default_factory=AuthHandoffs)

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

    def guard_emit(em: Emitter) -> Any:
        def guard(rule: str, detail: str, outcome: str, message: str) -> None:
            em.guardrail(rule, detail, outcome, message)

        return guard

    async def login(state: GraphState) -> dict[str, Any]:
        """시작 화면(또는 설정한 로그인 화면)이 로그인 화면이면 로그인하거나 사용자에게 넘긴다."""
        em = deps.emitter(state)
        cfg = deps.config
        if cfg.explorer.mode == "stub":
            return {"auth": None}
        em.stage("explorer", "running")
        alias = state["alias"]
        attempts = state.get("login_attempts", 0) + 1
        if attempts > cfg.explorer.login_attempts:
            raise ExplorerError(
                f"로그인·인증을 {cfg.explorer.login_attempts}번 시도했지만 "
                "로그인 상태가 되지 않아 멈춥니다"
            )
        site = cfg.site(alias)
        if site.browser == "extension":
            em.log("explorer", "사용자 Chrome(--extension)의 로그인 상태를 그대로 씁니다")
            return {"auth": None, "login_attempts": attempts}
        if deps.llm is None:
            raise ExplorerError("로그인 판별에 쓸 LLM이 설정되지 않았습니다")

        origins = cfg.allowed_origins(alias, state["url"])
        session = cfg.session_path(alias)
        had_session = session.exists()
        if had_session:
            register_session_secrets(session)
            em.log("explorer", "저장된 로그인 세션을 불러옵니다")
        target = site.login_url or state["url"]
        credentials = load_site_credentials(alias)
        # 로그인 브라우저 산출물(로그인 화면 스냅샷·세션 임시 파일)은 세션 폴더에 두고 끝나면 지운다
        staging = staging_dir(session, "login")
        with secrets_file(credentials) as secret_path:
            async with McpBrowser(
                origins,
                staging,
                headless=cfg.explorer.headless,
                secrets_file=secret_path,
                storage_state=session if had_session else None,
                caps=["storage"],
            ) as mcp:
                em.log(
                    "explorer", f"Playwright MCP 브라우저 시작, 허용 origin: {', '.join(origins)}"
                )
                browser = GuardedBrowser(mcp, origins, guard_emit(em))
                try:
                    check = await check_login(
                        mcp=mcp,
                        browser=browser,
                        detector=LoginDetector(deps.llm),
                        run_id=state["run_id"],
                        url=target,
                        credentials=credentials,
                        session_path=session,
                        staging=staging,
                        log=lambda m: em.log("explorer", m),
                    )
                except BrowserActionError as e:
                    raise ExplorerError(f"시작 화면을 열 수 없습니다: {target} ({e})") from e
        shutil.rmtree(staging, ignore_errors=True)

        if check.status == "ok":
            if check.kind == "none":
                em.log(
                    "explorer",
                    "저장된 세션으로 로그인된 상태입니다"
                    if had_session
                    else "로그인 화면이 아닙니다. 로그인 없이 진행합니다",
                )
            else:
                em.log(
                    "explorer",
                    f"{check.reason}. 세션을 저장했습니다 "
                    "(계정 값은 코드가 입력, LLM은 입력란만 찾음)",
                )
            return {
                "auth": None,
                "login_attempts": attempts,
                "login_url": check.login_url or state.get("login_url"),
            }

        if had_session:
            session.unlink(missing_ok=True)
            em.log("explorer", "저장된 로그인 세션이 만료되어 삭제했습니다", "warn")
        request = AuthRequest(
            login_kind=check.kind, reason=check.reason, url=check.login_url or target
        )
        em.log("explorer", f"사용자 인증이 필요합니다: {check.reason}", "warn")
        return {
            "auth": request.model_dump(),
            "login_attempts": attempts,
            "login_url": check.login_url,
        }

    def after_login(state: GraphState) -> str:
        return "auth_gate" if state.get("auth") else "explorer"

    async def auth_gate(state: GraphState) -> dict[str, Any]:
        """사용자가 인증할 브라우저 창을 띄우고 인증 대기를 알린다."""
        em = deps.emitter(state)
        cfg = deps.config
        alias = state["alias"]
        request = AuthRequest.model_validate(state["auth"])
        origins = cfg.allowed_origins(alias, state["url"])
        # 인증 브라우저 산출물도 세션처럼 다룬다 (next-pjt 밖, git 제외, 닫을 때 지움)
        staging = staging_dir(cfg.session_path(alias), "auth")

        def factory() -> McpBrowser:
            return McpBrowser(
                origins, staging, headless=cfg.explorer.auth_headless, caps=["storage"]
            )

        await deps.auth.open(alias, factory, request.url, staging)
        em.stage("explorer", "waiting", "인증 대기")
        em.status("awaiting_auth", auth=request.model_dump(by_alias=True))
        em.log(
            "gate",
            "사용자 인증 대기: 브라우저 창에서 인증을 마치고 콘솔에서 '인증 완료'를 누르세요. "
            "인증하는 동안 에이전트는 브라우저를 조작하지 않습니다",
        )
        return {}

    async def auth_wait(state: GraphState) -> Command[str]:
        raw = interrupt({"gate": "auth"})
        decision = AuthDecision.model_validate(raw)
        em = deps.emitter(state)
        alias = state["alias"]
        if decision.action == "cancel":
            await deps.auth.close(alias)
            em.stage("explorer", "stopped")
            em.log("gate", "사용자 인증을 취소해 실행을 멈춥니다", "warn")
            em.status("stopped")
            return Command(goto=END)
        try:
            saved = await deps.auth.save(alias, deps.config.session_path(alias))
        finally:
            await deps.auth.close(alias)
        em.stage("explorer", "running")
        em.status("running")
        if saved:
            em.log("gate", "인증 완료: 세션을 저장했습니다. 로그인 상태를 다시 확인합니다")
        else:
            em.log(
                "gate", "인증 브라우저가 닫혀 있어(서버 재시작 등) 다시 인증을 요청합니다", "warn"
            )
        return Command(goto="login", update={"auth": None})

    def site_browser(state: GraphState) -> McpBrowser:
        """수집용 브라우저: 저장된 로그인 세션(있으면)과 사이트 설정(extension)으로 연다."""
        cfg = deps.config
        alias = state["alias"]
        session = cfg.session_path(alias)
        return McpBrowser(
            cfg.allowed_origins(alias, state["url"]),
            cfg.site_dir(alias) / "crawl" / "_mcp",
            headless=cfg.explorer.headless,
            storage_state=session if session.exists() else None,
            extension=cfg.site(alias).browser == "extension",
        )

    def screen_saver(
        browser: GuardedBrowser, store: CrawlStore, em: Emitter, captures: list[ScreenCapture]
    ) -> Callable[[str, str], Awaitable[ScreenResult | None]]:
        async def save_screen(url: str, title: str) -> ScreenResult | None:
            """화면 원본을 저장하고 파생 파일을 만든다. 실패해도 수집은 계속한다."""
            try:
                raw = await capture_screen(browser, url, title, secrets.mask)
                store.save_raw(raw)
                layout, components, _ = store.derive(raw.capture.screen_id)
            except (BrowserActionError, OSError, ValueError) as e:
                em.log("explorer", f"화면 저장 실패: {url} ({e})", "warn")
                return None
            captures.append(raw.capture)
            em.log(
                "explorer",
                f"화면 저장: {raw.capture.screen_id} "
                f"(영역 {len(layout.regions)}·표 {len(components.tables)}·"
                f"폼 {len(components.forms)}·버튼 {len(components.buttons)})",
            )
            return ScreenResult(raw.capture, raw.dom_html, layout, components)

        return save_screen

    async def explorer(state: GraphState) -> Command[str]:
        em = deps.emitter(state)
        em.stage("explorer", "running")
        if deps.config.explorer.mode == "stub":
            em.log("explorer", f"{STUB}대상 {state['url']} — 브라우저 없이 예시 화면을 씁니다")
            await em.step()
            em.metrics(screens_collected=stubs.TOTAL_COLLECTED_SCREENS)
            em.stage("explorer", "done", f"{stubs.TOTAL_COLLECTED_SCREENS}개 화면")
            return Command(goto="analyst")

        cfg = deps.config
        alias = state["alias"]
        origins = cfg.allowed_origins(alias, state["url"])
        session = cfg.session_path(alias)
        has_session = session.exists()
        extension = cfg.site(alias).browser == "extension"
        async with site_browser(state) as mcp:
            em.log(
                "explorer", "화면 수집 시작" + (" (저장된 로그인 세션 사용)" if has_session else "")
            )
            browser = GuardedBrowser(mcp, origins, guard_emit(em))
            store = CrawlStore(cfg.site_dir(alias) / "crawl")
            captures: list[ScreenCapture] = []
            save_screen = screen_saver(browser, store, em, captures)

            def progress(graph: SiteGraph) -> None:
                # 콘솔이 사이트맵을 바로 다시 읽도록 화면이 늘 때마다 저장하고 지표를 보낸다
                store.save_graph(graph)
                em.metrics(screens_collected=len(graph.nodes))

            limits = MapLimits(
                max_screens=cfg.explorer.max_screens,
                max_depth=cfg.explorer.max_depth,
                max_per_pattern=cfg.explorer.max_per_pattern,
            )
            try:
                graph = await map_site(
                    browser,
                    state["url"],
                    limits,
                    save_screen,
                    lambda m: em.log("explorer", m),
                    login_url=state.get("login_url"),
                    on_progress=progress,
                )
            except SessionExpiredError as e:
                session.unlink(missing_ok=True)
                em.log("explorer", f"세션 만료를 감지해 다시 인증합니다: {e}", "warn")
                return Command(goto="login")
            if not extension:
                await browser.call("browser_close", {})
        store.save_graph(graph)
        store.update_manifest(alias, captures)
        em.metrics(screens_collected=len(graph.nodes))
        count = Counter(e.status for e in graph.edges)
        em.log(
            "explorer",
            f"사이트맵: 화면 {len(graph.nodes)}개, 메뉴 {len(graph.menu)}개, "
            f"이동 {count['followed'] + count['duplicate']}건, 차단 {count['blocked']}건, "
            f"건너뜀 {count['skipped']}건, 상한 {count['limit']}건"
            + (" (화면 수 상한에 닿음)" if graph.truncated else "")
            + f" — next-pjt/{alias}/crawl/graph.json",
        )
        return Command(goto="walker")

    async def walker(state: GraphState) -> Command[str]:
        """Hypothesize · Walk: 유스케이스 후보를 세우고 점수 높은 것부터 실제로 걸어 본다."""
        em = deps.emitter(state)
        cfg = deps.config
        alias = state["alias"]
        store = CrawlStore(cfg.site_dir(alias) / "crawl")
        graph = store.load_graph()
        if not cfg.explorer.walk_enabled or deps.llm is None or graph is None or not graph.nodes:
            em.stage("explorer", "done", "흐름 걷기 생략")
            return Command(goto="analyst")

        em.log("explorer", "유스케이스 후보 만들기 (사이트맵 요약을 LLM에 1회 전달)")
        try:
            hypotheses = await hypothesize(deps.llm, state["run_id"], graph, store)
        except ValueError as e:
            em.log("explorer", f"유스케이스 후보를 만들지 못했습니다: {e}", "warn")
            em.stage("explorer", "done", f"{len(graph.nodes)}개 화면 · 후보 없음")
            return Command(goto="analyst")
        store.save_hypotheses(hypotheses)
        em.metrics(screens_collected=len(graph.nodes))
        em.log(
            "explorer",
            f"사이트 성격(1차): {hypotheses.site.domain} · 후보 {len(hypotheses.candidates)}개: "
            + ", ".join(f"{c.name}({c.total})" for c in hypotheses.candidates),
        )

        origins = cfg.allowed_origins(alias, state["url"])
        known = {n.screen_id for n in graph.nodes}
        captures: list[ScreenCapture] = []
        limits = WalkLimits(
            max_steps=cfg.explorer.walk_max_steps,
            max_candidates=cfg.explorer.walk_max_candidates,
            target_completed=cfg.explorer.walk_target,
        )
        decider = WalkDecider(deps.llm)
        async with site_browser(state) as mcp:
            browser = GuardedBrowser(mcp, origins, guard_emit(em))
            save_screen = screen_saver(browser, store, em, captures)

            async def capture_new(url: str, title: str) -> None:
                """걷다가 처음 닿은 화면도 원본·파생을 저장한다."""
                if screen_id_for(url) not in known:
                    known.add(screen_id_for(url))
                    await save_screen(url, title)

            async def decide(
                candidate: UseCaseCandidate, steps: list[FlowStep], page: ToolResult
            ) -> WalkDecision:
                return await decider.decide(state["run_id"], candidate, steps, page)

            report = await run_walk(
                browser,
                hypotheses,
                decide,
                capture_new,
                store,
                limits,
                lambda m: em.log("explorer", m),
                # 흐름 하나가 끝날 때마다 콘솔이 걷기 결과를 다시 읽게 한다
                on_flow=lambda _t: em.metrics(screens_collected=len(graph.nodes) + len(captures)),
            )
            if cfg.site(alias).browser != "extension":
                await browser.call("browser_close", {})
        store.update_manifest(alias, captures)
        total = len(graph.nodes) + len(captures)
        em.metrics(screens_collected=total)
        done = len(report.completed)
        em.log(
            "explorer",
            f"흐름 걷기: 완주 {done}개 / 시도 {len(report.traces)}개 "
            f"(목표 {limits.target_completed}개) — next-pjt/{alias}/crawl/flows/",
            "info" if done >= 2 else "warn",
        )
        em.stage("explorer", "done", f"{total}개 화면 · 완주 {done}개")
        return Command(goto="analyst")

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
        if deps.config.session_path(state["alias"]).exists():
            em.log(
                "system",
                "로그인 세션 파일이 남아 있습니다. "
                "더 수집하지 않을 거면 결과 화면에서 삭제하세요 (G10)",
            )
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

    async def designer(state: GraphState) -> Command[str]:
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
        # 일반 변경 화면은 자동 승인하고, 레이아웃 대폭 변경 화면만 사용자 승인을 받는다
        regular = [s for s in design.screens if not s.major_change]
        for s in regular:
            s.state = "approved"
            s.auto_approved = True
        major = len(design.screens) - len(regular)
        update = {"design": design.model_dump()}
        if regular:
            em.log("gate", f"일반 변경 화면 {len(regular)}개 자동 승인")
        if major == 0:
            em.stage("designReview", "done", "대폭 변경 없음 · 자동 승인")
            em.log("gate", "대폭 변경 화면이 없어 승인 2를 건너뜁니다")
            return Command(goto="builder", update=update)
        em.log("gate", f"승인 2 대기: 대폭 변경 화면 {major}개 디자인 확인")
        return Command(goto="design_gate", update=update)

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
    graph.add_node("login", login)
    graph.add_node("auth_gate", auth_gate)
    graph.add_node("auth_wait", auth_wait, destinations=("login", END))
    graph.add_node("explorer", explorer, destinations=("walker", "analyst", "login"))
    graph.add_node("walker", walker, destinations=("analyst",))
    graph.add_node("analyst", analyst)
    graph.add_node("analysis_gate", analysis_gate)
    graph.add_node(
        "analysis_review", analysis_review, destinations=("designer", "analysis_gate", END)
    )
    graph.add_node("designer", designer, destinations=("design_gate", "builder"))
    graph.add_node("design_gate", design_gate)
    graph.add_node("design_review", design_review, destinations=("builder", "design_gate", END))
    graph.add_node("builder", builder)
    graph.add_node("verifier", verifier)
    graph.add_node("finish", finish)
    graph.add_edge(START, "router")
    graph.add_edge("router", "login")
    graph.add_conditional_edges("login", after_login, ["auth_gate", "explorer"])
    graph.add_edge("auth_gate", "auth_wait")
    graph.add_edge("analyst", "analysis_gate")
    graph.add_edge("analysis_gate", "analysis_review")
    graph.add_edge("design_gate", "design_review")
    graph.add_edge("builder", "verifier")
    graph.add_edge("verifier", "finish")
    graph.add_edge("finish", END)
    return graph.compile(checkpointer=checkpointer)
