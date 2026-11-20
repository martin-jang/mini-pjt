"""콘솔 ↔ 에이전트 API 데이터 구조. ui/src/api/types.ts 와 같은 모양(camelCase JSON)이다."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

RunKind = Literal["new", "extend"]
RunStatus = Literal[
    "running", "awaiting_auth", "awaiting_analysis", "awaiting_design", "done", "stopped", "failed"
]
# 로그인 화면 유형: 로그인 아님 / 아이디·비밀번호 / 공동·공인인증서 / 간편인증 / 판단 어려움
LoginKind = Literal["none", "id_pw", "certificate", "simple_auth", "unknown"]
StageId = Literal[
    "explorer", "analyst", "analysisReview", "designer", "designReview", "builder", "verifier"
]
StageState = Literal["pending", "running", "waiting", "done", "stopped"]
LogLevel = Literal["info", "warn", "block"]
GuardrailOutcome = Literal["masked", "blocked", "skipped", "approved"]
DataMode = Literal["mock", "legacy"]
VariantDecision = Literal["unify", "prop", "hold"]
ReviewAction = Literal["approve", "revise", "reject"]
ScreenReviewState = Literal["pending", "approved", "revise"]

STAGE_ORDER: list[StageId] = [
    "explorer",
    "analyst",
    "analysisReview",
    "designer",
    "designReview",
    "builder",
    "verifier",
]


class ApiModel(BaseModel):
    """JSON은 camelCase, 파이썬은 snake_case."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class StageInfo(ApiModel):
    id: StageId
    state: StageState = "pending"
    note: str | None = None


class LogLine(ApiModel):
    at: str
    source: str
    level: LogLevel
    message: str


class GuardrailEvent(ApiModel):
    at: str
    rule: str
    detail: str
    outcome: GuardrailOutcome


class RunMetrics(ApiModel):
    screens_collected: int = 0
    llm_calls: int = 0
    llm_limit: int = 0


class RunTiming(ApiModel):
    started_at: str
    finished_at: str | None = None
    wait_ms: int = 0
    waiting_since: str | None = None


# ── 분석 리뷰 ─────────────────────────────


class Evidence(ApiModel):
    screen: str
    path: str


class SiteProfile(ApiModel):
    domain: str
    users: str
    core_tasks: str
    confidence: float
    summary: str
    evidence: list[Evidence]


class HappyPathCandidate(ApiModel):
    id: str
    title: str
    steps: list[str]
    reason: str
    recommended: bool


class DataModeOption(ApiModel):
    mode: DataMode
    title: str
    summary: str
    reasons: list[str]
    caveat: str | None = None
    recommended: bool


class VariantGroup(ApiModel):
    id: str
    name: str
    selectors: list[str]
    screen_count: int
    decision: VariantDecision
    reason: str


class AnalysisReview(ApiModel):
    profile: SiteProfile
    happy_paths: list[HappyPathCandidate]
    data_modes: list[DataModeOption]
    variants: list[VariantGroup]


class ApprovedAnalysis(ApiModel):
    happy_path_ids: list[str]
    data_mode: DataMode
    variant_decisions: dict[str, VariantDecision]


class AnalysisDecision(ApprovedAnalysis):
    action: ReviewAction
    comment: str | None = None


# ── 디자인 확인 ─────────────────────────────


class LayoutSketch(ApiModel):
    nav: Literal["left", "top", "none"]
    blocks: list[str]


class DesignChange(ApiModel):
    """바뀐 점과 그렇게 바꾼 이유."""

    what: str
    why: str

    @model_validator(mode="before")
    @classmethod
    def _from_text(cls, value: Any) -> Any:
        """예전 형식(문자열 하나)으로 저장된 체크포인트도 읽는다."""
        return {"what": value, "why": ""} if isinstance(value, str) else value


class DesignScreen(ApiModel):
    id: str
    name: str
    path: str
    major_change: bool
    changes: list[DesignChange]
    state: ScreenReviewState = "pending"
    # 일반 변경 화면은 자동 승인한다 (대폭 변경 화면만 사용자 승인)
    auto_approved: bool = False
    asis: LayoutSketch
    tobe: LayoutSketch


class DesignReview(ApiModel):
    design_system: str
    screens: list[DesignScreen]


class DesignDecision(ApiModel):
    # 일반 변경 화면은 자동 승인되므로 대폭 변경 화면만 승인·수정 요청한다
    action: Literal["approveScreen", "revise", "rejectAll"]
    screen_id: str | None = None
    comment: str | None = None


# ── 결과 ─────────────────────────────


class GeneratedScreen(ApiModel):
    name: str
    path: str
    happy_path: str | None = None
    preserved: int
    total: int


class VerificationItem(ApiModel):
    id: str
    label: str
    detail: str
    passed: bool


class Decision(ApiModel):
    label: str
    value: str


class RunResult(ApiModel):
    output_dir: str
    preview_url: str
    total_screens: int
    screens: list[GeneratedScreen]
    components: list[str]
    decisions: list[Decision]
    verification: list[VerificationItem]


# ── 실행 ─────────────────────────────


class SiteSummary(ApiModel):
    alias: str
    url: str
    status: RunStatus


class AuthRequest(ApiModel):
    """사용자에게 넘긴 인증 (콘솔 "인증 대기" 카드)."""

    login_kind: LoginKind
    reason: str
    url: str


class AuthDecision(ApiModel):
    """done: 브라우저에서 인증을 마침, cancel: 실행을 멈춤."""

    action: Literal["done", "cancel"]


class SiteMapScreen(ApiModel):
    screen_id: str
    title: str
    url: str
    depth: int
    tables: int
    forms: int
    buttons: int
    # 이 화면으로 들어오는 이동 수 (메뉴·링크)
    inbound: int


class SiteMapMenuItem(ApiModel):
    label: str
    screen_id: str | None = None
    children: list[SiteMapMenuItem] = Field(default_factory=list)


class SiteMapLink(ApiModel):
    """따라가지 않은 링크와 이유 (차단·건너뜀·상한·실패)."""

    label: str
    url: str | None = None
    status: str
    reason: str


class SiteMapView(ApiModel):
    """콘솔용 사이트맵 요약 (crawl/graph.json에서 만든다)."""

    screens: list[SiteMapScreen] = Field(default_factory=list)
    menu: list[SiteMapMenuItem] = Field(default_factory=list)
    edge_counts: dict[str, int] = Field(default_factory=dict)
    not_followed: list[SiteMapLink] = Field(default_factory=list)
    truncated: bool = False


class RunDetail(SiteSummary):
    kind: RunKind
    stages: list[StageInfo]
    metrics: RunMetrics
    timing: RunTiming
    logs: list[LogLine] = Field(default_factory=list)
    guardrails: list[GuardrailEvent] = Field(default_factory=list)
    auth: AuthRequest | None = None
    # 저장된 로그인 세션 파일이 있는지 (G10: 실행이 끝나면 삭제 여부를 묻는다)
    session_saved: bool = False
    sitemap: SiteMapView | None = None
    analysis: AnalysisReview | None = None
    approved_analysis: ApprovedAnalysis | None = None
    design: DesignReview | None = None
    result: RunResult | None = None


# ── /query ─────────────────────────────


class QueryRequest(ApiModel):
    """콘솔의 단일 진입점. url이 있으면 새 요청 폼(Router LLM 생략), question이면 Router가 분류."""

    alias: str | None = None
    url: str | None = None
    kind: RunKind | None = None
    question: str | None = None


class QueryTable(ApiModel):
    columns: list[str]
    rows: list[list[str]]


class StartSuggestion(ApiModel):
    """Router가 생성·확장 요청으로 분류했을 때 콘솔이 새 요청 폼을 채우는 값."""

    kind: RunKind
    url: str | None = None
    alias: str | None = None


class QueryAnswer(ApiModel):
    kind: Literal["answer", "rejected", "start"]
    text: str
    start: StartSuggestion | None = None
    table: QueryTable | None = None
    sources: list[str] = Field(default_factory=list)


class QueryResponse(ApiModel):
    intent: Literal["new", "extend", "query", "out_of_scope"]
    run: RunDetail | None = None
    answer: QueryAnswer | None = None
