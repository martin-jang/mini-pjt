"""수집 데이터 구조 (T07b): `next-pjt/<별칭>/crawl/`의 원본·파생 파일 모델과 저장소.

원칙: 원본은 한 번 수집하고, 파생 데이터는 여러 번 만든다 (SERVICE.md 수집 데이터 구조).
- 원본 `screens/<id>/raw/`: capture.json, screenshot.png, aria.yml, dom.min.html,
  network.json, console.log
- 파생 `screens/<id>/derived/`: layout.json, components.json, tokens.json
  (원본 dom.min.html만으로 다시 만든다)
- 모든 파일 구조는 Pydantic 모델이고 schema_version을 붙인다

다시 만들기: python -m legacy2next.crawl <crawl 폴더>
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field

SCHEMA_VERSION = 1
SchemaVersion = Literal[1]

RAW_FILES = (
    "capture.json",
    "screenshot.png",
    "aria.yml",
    "dom.min.html",
    "network.json",
    "console.log",
)
DERIVED_FILES = ("layout.json", "components.json", "tokens.json")
SCREEN_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class Versioned(BaseModel):
    schema_version: SchemaVersion = SCHEMA_VERSION


# ── 원본 ─────────────────────────────


class Viewport(BaseModel):
    width: int
    height: int


class ScreenCapture(Versioned):
    """raw/capture.json: 수집 시점 정보."""

    screen_id: str
    url: str
    title: str
    captured_at: str
    viewport: Viewport | None = None


class NetworkRequest(BaseModel):
    method: str
    url: str
    status: int | None = None
    status_text: str = ""


class NetworkLog(Versioned):
    """raw/network.json: 화면을 연 뒤의 요청 목록 (헤더·본문은 저장하지 않는다, G10)."""

    requests: list[NetworkRequest] = Field(default_factory=list)


class RawCapture(BaseModel):
    """한 화면의 원본 묶음 (저장 전, 마스킹을 거친 값)."""

    capture: ScreenCapture
    screenshot_png: bytes | None = None
    aria_yaml: str
    dom_html: str
    network: NetworkLog
    console_log: str


# ── 파생 ─────────────────────────────


class Box(BaseModel):
    x: int
    y: int
    width: int
    height: int


RegionRole = Literal["header", "nav", "main", "aside", "footer"]


class Region(BaseModel):
    role: RegionRole
    box: Box
    selector: str  # tag#id.class (근거 확인용)


class Density(BaseModel):
    elements: int
    interactive: int
    text_blocks: int
    # 뷰포트 한 화면 높이당 상호작용 요소 수
    interactive_per_screen: float


class Layout(Versioned):
    """derived/layout.json: 영역 배치, 메뉴 방식, 밀도, 본문 그리드."""

    viewport: Viewport
    page_height: int
    regions: list[Region] = Field(default_factory=list)
    menu: Literal["top", "left", "right", "none"] = "none"
    density: Density
    main_columns: int = 1


class FormField(BaseModel):
    label: str
    name: str = ""
    type: str
    required: bool = False
    pattern: str | None = None
    max_length: int | None = None
    options: list[str] = Field(default_factory=list)


class Form(BaseModel):
    method: str = "get"
    fields: list[FormField] = Field(default_factory=list)
    submits: list[str] = Field(default_factory=list)


class Table(BaseModel):
    headers: list[str]
    rows: int


class Paging(BaseModel):
    labels: list[str]


class Components(Versioned):
    """derived/components.json: 표(컬럼 순서), 폼(라벨·타입·필수·검증), 버튼, 탭, 페이징."""

    tables: list[Table] = Field(default_factory=list)
    forms: list[Form] = Field(default_factory=list)
    buttons: list[str] = Field(default_factory=list)
    tabs: list[list[str]] = Field(default_factory=list)
    paging: list[Paging] = Field(default_factory=list)
    links: int = 0


class TokenCount(BaseModel):
    value: str
    count: int


class Tokens(Versioned):
    """derived/tokens.json: 화면에 실제 적용된 색·폰트·간격 (많이 쓰인 순)."""

    text_colors: list[TokenCount] = Field(default_factory=list)
    background_colors: list[TokenCount] = Field(default_factory=list)
    # 회색이 아닌 색 (주색 후보)
    accent_colors: list[TokenCount] = Field(default_factory=list)
    font_families: list[TokenCount] = Field(default_factory=list)
    font_sizes: list[TokenCount] = Field(default_factory=list)
    font_weights: list[TokenCount] = Field(default_factory=list)
    spacing: list[TokenCount] = Field(default_factory=list)
    radius: list[TokenCount] = Field(default_factory=list)


# ── 사이트맵 (T07c) ─────────────────────────────

LinkArea = Literal["header", "nav", "main", "aside", "footer", "other"]


class PageLink(BaseModel):
    """화면 안의 링크. kind: url(주소로 이동), script(주소 없음, 클릭해야 함), download, none."""

    label: str
    href: str
    kind: Literal["url", "script", "download", "none"]
    area: LinkArea


class MenuItem(BaseModel):
    label: str
    href: str | None = None
    # 이 메뉴로 수집한 화면 (못 갔으면 None)
    screen_id: str | None = None
    children: list[MenuItem] = Field(default_factory=list)


class GraphNode(BaseModel):
    screen_id: str
    url: str
    title: str
    depth: int
    # 같은 형태 URL 묶음 (숫자 경로·숫자 값을 뺀 모양)
    pattern: str
    regions: list[str] = Field(default_factory=list)
    tables: int = 0
    forms: int = 0
    buttons: int = 0


EdgeStatus = Literal["followed", "duplicate", "blocked", "skipped", "failed", "limit"]


class GraphEdge(BaseModel):
    """화면 → 화면 이동. 따라가지 않은 링크도 이유와 함께 남긴다."""

    source: str
    target: str | None = None
    label: str
    url: str | None = None
    via: Literal["link", "click"]
    area: LinkArea
    status: EdgeStatus
    reason: str = ""


class SiteGraph(Versioned):
    """crawl/graph.json: 사이트맵 (화면 노드 + 이동 엣지 + 메뉴 트리). 조회만, LLM 호출 없음."""

    start_url: str
    generated_at: str
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    menu: list[MenuItem] = Field(default_factory=list)
    # 화면 수·깊이 상한에 닿아 멈췄는지
    truncated: bool = False


# ── 유스케이스 후보·흐름 (T07d) ─────────────────────────────


class SiteGuess(BaseModel):
    """사이트맵만 보고 한 사이트 성격 1차 추론 (Analyst가 T10에서 다시 본다)."""

    domain: str
    users: str
    core_tasks: list[str] = Field(default_factory=list)


class CandidateScore(BaseModel):
    """0~5점: 메뉴에서 눈에 띄는 정도, 업무 완결성, 도메인 상식, 화면 재사용도."""

    menu: int = Field(ge=0, le=5)
    completeness: int = Field(ge=0, le=5)
    domain: int = Field(ge=0, le=5)
    reuse: int = Field(ge=0, le=5)

    @property
    def total(self) -> int:
        return self.menu + self.completeness + self.domain + self.reuse


class UseCaseCandidate(BaseModel):
    id: str
    name: str
    goal: str
    # view: 조회→상세, search: 검색→결과, input: 입력→확인→완료
    kind: Literal["view", "search", "input", "other"]
    start_screen_id: str
    start_url: str
    expected_steps: list[str] = Field(default_factory=list)
    score: CandidateScore
    total: int = 0
    reason: str


class Hypotheses(Versioned):
    """crawl/hypotheses.json: 사이트 성격 1차 추론과 유스케이스 후보 (점수 높은 순)."""

    generated_at: str
    site: SiteGuess
    candidates: list[UseCaseCandidate] = Field(default_factory=list)


class FlowTarget(BaseModel):
    """재실행 기준 요소: 접근성 역할 + 이름 (Playwright getByRole과 같은 기준)."""

    role: str
    name: str


FlowAction = Literal["navigate", "click", "type", "select", "press_enter"]
# 끝나지 못한 이유: 데이터 없음, 인증 필요, 쓰기 동작 미승인, 화면·요소 못 찾음, 단계 상한, 그 외
FailKind = Literal["no_data", "needs_auth", "write_action", "not_found", "step_limit", "other"]


class FlowStep(BaseModel):
    index: int
    action: FlowAction
    target: FlowTarget | None = None
    # 입력 종류(검색어·날짜·숫자 등)와 넣은 값 (합성 값만, 계정 값은 넣지 않는다)
    input_kind: str | None = None
    value: str | None = None
    from_url: str
    from_screen_id: str
    to_url: str
    to_screen_id: str
    to_title: str
    network: list[NetworkRequest] = Field(default_factory=list)
    # Playwright MCP가 알려 준 실행 코드 (사람이 읽는 재실행 참고용)
    code: str = ""
    reason: str = ""


class ReplayResult(BaseModel):
    """재실행 스크립트로 LLM 없이 다시 걸은 결과."""

    ok: bool
    steps_done: int
    message: str
    llm_calls: int = 0
    at: str


class FlowTrace(Versioned):
    """crawl/flows/<flow_id>.json: 유스케이스 하나를 걸은 기록 (Flow Trace + 재실행 스크립트)."""

    flow_id: str
    name: str
    goal: str
    kind: str
    start_url: str
    status: Literal["completed", "failed"]
    fail_kind: FailKind | None = None
    reason: str
    steps: list[FlowStep] = Field(default_factory=list)
    llm_calls: int = 0
    started_at: str
    finished_at: str
    replay: ReplayResult | None = None


# ── manifest ─────────────────────────────


class ScreenEntry(BaseModel):
    screen_id: str
    url: str
    title: str
    captured_at: str


class CrawlManifest(Versioned):
    """crawl/manifest.json: 수집 시각, 화면·흐름 목록."""

    alias: str
    created_at: str
    updated_at: str
    screens: list[ScreenEntry] = Field(default_factory=list)
    flows: list[str] = Field(default_factory=list)


# ── 저장소 ─────────────────────────────


def screen_id_for(url: str) -> str:
    """URL로 화면 ID를 만든다: 경로 조각 + URL 해시 6자리 (같은 URL은 같은 ID)."""
    parts = urlsplit(url)
    slug = re.sub(r"[^a-z0-9]+", "-", parts.path.lower()).strip("-")[:40] or "home"
    digest = hashlib.sha1(f"{parts.path}?{parts.query}".encode()).hexdigest()[:6]
    return f"{slug}-{digest}"


class CrawlStore:
    """crawl 폴더 읽기·쓰기. 이 폴더 밖에는 쓰지 않는다 (G9)."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _inside(self, path: Path) -> Path:
        resolved = path.resolve()
        if not resolved.is_relative_to(self.root.resolve()):
            raise ValueError(f"crawl 폴더 밖 경로입니다: {path}")
        return path

    def screen_dir(self, screen_id: str) -> Path:
        if not SCREEN_ID.match(screen_id):
            raise ValueError(f"화면 ID 형식이 아닙니다: {screen_id!r}")
        return self._inside(self.root / "screens" / screen_id)

    def save_raw(self, raw: RawCapture) -> Path:
        raw_dir = self.screen_dir(raw.capture.screen_id) / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / "capture.json").write_text(raw.capture.model_dump_json(indent=2), "utf-8")
        if raw.screenshot_png is not None:
            (raw_dir / "screenshot.png").write_bytes(raw.screenshot_png)
        (raw_dir / "aria.yml").write_text(raw.aria_yaml, "utf-8")
        (raw_dir / "dom.min.html").write_text(raw.dom_html, "utf-8")
        (raw_dir / "network.json").write_text(raw.network.model_dump_json(indent=2), "utf-8")
        (raw_dir / "console.log").write_text(raw.console_log, "utf-8")
        return raw_dir

    def derive(self, screen_id: str) -> tuple[Layout, Components, Tokens]:
        """원본 dom.min.html만 읽어 파생 파일을 (다시) 만든다."""
        from .derive import derive_all

        screen = self.screen_dir(screen_id)
        html = (screen / "raw" / "dom.min.html").read_text("utf-8")
        layout, components, tokens = derive_all(html)
        out = screen / "derived"
        out.mkdir(parents=True, exist_ok=True)
        (out / "layout.json").write_text(layout.model_dump_json(indent=2), "utf-8")
        (out / "components.json").write_text(components.model_dump_json(indent=2), "utf-8")
        (out / "tokens.json").write_text(tokens.model_dump_json(indent=2), "utf-8")
        return layout, components, tokens

    def screen_ids(self) -> list[str]:
        folder = self.root / "screens"
        if not folder.exists():
            return []
        return sorted(p.name for p in folder.iterdir() if (p / "raw" / "dom.min.html").exists())

    def rederive_all(self) -> list[str]:
        ids = self.screen_ids()
        for screen_id in ids:
            self.derive(screen_id)
        return ids

    def save_graph(self, graph: SiteGraph) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._inside(self.root / "graph.json")
        path.write_text(graph.model_dump_json(indent=2), "utf-8")

    def load_graph(self) -> SiteGraph | None:
        path = self.root / "graph.json"
        if not path.exists():
            return None
        return SiteGraph.model_validate_json(path.read_text("utf-8"))

    def save_hypotheses(self, hypotheses: Hypotheses) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._inside(self.root / "hypotheses.json")
        path.write_text(hypotheses.model_dump_json(indent=2), "utf-8")

    def load_hypotheses(self) -> Hypotheses | None:
        path = self.root / "hypotheses.json"
        if not path.exists():
            return None
        return Hypotheses.model_validate_json(path.read_text("utf-8"))

    def save_flow(self, trace: FlowTrace) -> Path:
        if not SCREEN_ID.match(trace.flow_id):
            raise ValueError(f"흐름 ID 형식이 아닙니다: {trace.flow_id!r}")
        folder = self._inside(self.root / "flows")
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{trace.flow_id}.json"
        path.write_text(trace.model_dump_json(indent=2), "utf-8")
        return path

    def load_flows(self) -> list[FlowTrace]:
        folder = self.root / "flows"
        if not folder.exists():
            return []
        return [
            FlowTrace.model_validate_json(f.read_text("utf-8"))
            for f in sorted(folder.glob("*.json"))
        ]

    def load_manifest(self) -> CrawlManifest | None:
        path = self.root / "manifest.json"
        if not path.exists():
            return None
        return CrawlManifest.model_validate_json(path.read_text("utf-8"))

    def update_manifest(self, alias: str, captures: list[ScreenCapture]) -> CrawlManifest:
        """수집한 화면을 manifest에 더한다 (같은 화면 ID는 새 값으로 바꾼다)."""
        now = now_iso()
        manifest = self.load_manifest() or CrawlManifest(
            alias=alias, created_at=now, updated_at=now
        )
        by_id = {s.screen_id: s for s in manifest.screens}
        for c in captures:
            by_id[c.screen_id] = ScreenEntry(
                screen_id=c.screen_id, url=c.url, title=c.title, captured_at=c.captured_at
            )
        manifest.screens = list(by_id.values())
        flows = {f.flow_id for f in self.load_flows()}
        manifest.flows = sorted(flows | set(manifest.flows))
        manifest.updated_at = now
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "manifest.json").write_text(manifest.model_dump_json(indent=2), "utf-8")
        return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="저장된 원본으로 파생 파일을 다시 만든다")
    parser.add_argument("crawl_dir", type=Path, help="next-pjt/<별칭>/crawl")
    args = parser.parse_args(argv)
    ids = CrawlStore(args.crawl_dir).rederive_all()
    sys.stdout.write(f"파생 파일을 다시 만든 화면 {len(ids)}개\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
