"""T07e 테스트 데이터 없음 대응.

단위: data_schema 추론(출처·타입), 합성 값 형식, G11(출처 없는 레코드 거부),
빈 결과 → 조건 넓혀 다시 조회해 찾음(가짜 브라우저), 계속 비면 부분 완주.
통합(실제 MCP + 시험 사이트 자료실 + 가짜 LLM): 부분 완주 기록, fixtures/ 합성 데이터,
화면별 데이터 출처.
"""

import json
import shutil
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from legacy2next.api import create_app
from legacy2next.browser import MCP_CLI, GuardedBrowser, ToolResult
from legacy2next.config import AgentConfig
from legacy2next.crawl import (
    CandidateScore,
    CrawlStore,
    DataField,
    FixtureRecord,
    FixtureSet,
    UseCaseCandidate,
)
from legacy2next.derive import derive_data_schema, looks_empty
from legacy2next.testdata import synthesize, synthetic_value
from legacy2next.walker import WalkDecision, walk_flow

from .fixtures.site_server import start_site

B = 'data-l2n-box="0,0,10,10"'
LIST_HTML = f"""<html><body {B}><table {B}><thead {B}><tr {B}><th {B}>번호</th><th {B}>신청자</th>
<th {B}>신청일</th><th {B}>금액</th></tr></thead><tbody {B}>
<tr {B}><td {B}>1</td><td {B}>가나다</td><td {B}>2026-01-02</td><td {B}>1,000</td></tr>
</tbody></table></body></html>"""
EMPTY_HTML = f"""<html><body {B}><table {B}><thead {B}><tr {B}><th {B}>번호</th><th {B}>자료명</th>
<th {B}>등록일</th><th {B}>연락처</th></tr></thead><tbody {B}>
<tr {B}><td colspan="4" {B}>조회된 자료가 없습니다.</td></tr></tbody></table></body></html>"""
DETAIL_HTML = f"""<html><body {B}><table {B}><tr {B}><th {B}>제목</th><td {B}>안내</td></tr>
<tr {B}><th {B}>작성자</th><td {B}>관리자</td></tr></table></body></html>"""


def test_data_schema_source_and_types():
    observed = derive_data_schema(LIST_HTML)
    assert observed.source == "observed"
    entity = observed.entities[0]
    assert entity.kind == "list" and entity.observed_rows == 1
    assert [f.type for f in entity.fields] == ["number", "name", "date", "money"]

    inferred = derive_data_schema(EMPTY_HTML)
    assert inferred.source == "inferred" and inferred.entities[0].observed_rows == 0
    assert [f.type for f in inferred.entities[0].fields] == ["number", "text", "date", "phone"]

    detail = derive_data_schema(DETAIL_HTML)
    assert detail.entities[0].kind == "detail" and detail.source == "observed"

    synthetic = derive_data_schema(EMPTY_HTML, fixture="fixtures/x.json")
    assert synthetic.source == "synthetic" and synthetic.fixture == "fixtures/x.json"


def test_synthetic_values_follow_format_only():
    def field(kind: str) -> DataField:
        return DataField(name=kind, label=kind, type=kind)  # type: ignore[arg-type]

    assert synthetic_value(field("phone"), 3) == "010-0000-0003"
    assert synthetic_value(field("email"), 2) == "user2@example.com"
    assert synthetic_value(field("date"), 2) == "2026-01-08"
    schema = derive_data_schema(EMPTY_HTML)
    fixture = synthesize("archive-1", schema.entities[0])
    assert len(fixture.records) == 5 and all(r.source == "synthetic" for r in fixture.records)
    # 화면에서 본 실제 값은 합성 데이터에 들어가지 않는다
    assert "가나다" not in json.dumps(
        synthesize("l", derive_data_schema(LIST_HTML).entities[0]).model_dump(), ensure_ascii=False
    )


def test_records_without_synthetic_source_are_rejected_g11(tmp_path: Path):
    with pytest.raises(ValidationError):
        FixtureRecord.model_validate({"values": {"a": 1}})
    with pytest.raises(ValidationError):
        FixtureRecord.model_validate({"source": "observed", "values": {"a": 1}})
    with pytest.raises(ValidationError):
        FixtureSet.model_validate(
            {"screen_id": "x", "entity": "e", "source": "observed", "generated_at": "t"}
        )


def test_empty_result_phrases():
    assert looks_empty("조회된 자료가 없습니다.")
    assert looks_empty("검색 결과가 없습니다")
    assert looks_empty("No results found")
    assert not looks_empty("시스템 점검 안내")


# ── 빈 결과 → 조건 넓혀 다시 조회 (가짜 브라우저) ──

ORIGIN = "https://legacy.example.com"
EMPTY_PAGE = '- textbox "검색어" [ref=e1]\n- button "조회" [ref=e2]\n- cell "검색 결과가 없습니다."'
FULL_PAGE = '- textbox "검색어" [ref=e1]\n- button "조회" [ref=e2]\n- link "점검 안내" [ref=e3]'


class SearchSite:
    """검색어가 있으면 결과가 비고, 검색어를 지우고 조회하면 결과가 나온다."""

    def __init__(self, always_empty: bool = False) -> None:
        self.word = "없는말"
        self.searched = "없는말"  # 조회 버튼을 눌러야 결과가 바뀐다
        self.url = f"{ORIGIN}/list?q=없는말"
        self.always_empty = always_empty

    async def call(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        if name == "browser_type":
            self.word = arguments["text"]
        elif name == "browser_click":
            self.searched = self.word
            self.url = f"{ORIGIN}/list?q={self.word}"
        empty = self.always_empty or bool(self.searched)
        text = EMPTY_PAGE if empty else FULL_PAGE
        return ToolResult(text=text, page_url=self.url, page_title="목록")


def candidate() -> UseCaseCandidate:
    return UseCaseCandidate(
        id="uc-1",
        name="검색",
        goal="검색 결과 보기",
        kind="search",
        start_screen_id="s",
        start_url=f"{ORIGIN}/list?q=없는말",
        score=CandidateScore(menu=1, completeness=1, domain=1, reuse=1),
        reason="",
    )


def scripted(decisions: list[WalkDecision], notices: list[str | None]):
    async def decide(c: Any, steps: Any, page: Any, notice: str | None) -> WalkDecision:
        notices.append(notice)
        return decisions.pop(0)

    return decide


async def nothing(url: str, title: str) -> None:
    return None


async def test_widened_search_finds_data():
    notices: list[str | None] = []
    decide = scripted(
        [
            WalkDecision(action="type", target_ref="e1", text="", input_kind="검색어", reason=""),
            WalkDecision(action="click", target_ref="e2", reason=""),
            WalkDecision(action="done", reason="결과 도착"),
        ],
        notices,
    )
    browser = GuardedBrowser(SearchSite(), [ORIGIN], lambda *e: None)
    trace = await walk_flow(browser, candidate(), decide, nothing, 8)
    assert trace.status == "completed"
    assert trace.data_recovery and trace.data_recovery.result == "found"
    assert trace.data_recovery.widened_steps == [1, 2]
    assert notices[0] and notices[-1] is None  # 빈 결과일 때만 LLM에 넓히라고 알린다


async def test_still_empty_becomes_partial_and_done_on_empty_is_not_completion():
    decide = scripted(
        [
            WalkDecision(action="type", target_ref="e1", text="", input_kind="검색어", reason=""),
            WalkDecision(action="click", target_ref="e2", reason=""),
            WalkDecision(action="done", reason="결과 화면"),  # 빈 화면에서 끝내려 함
        ],
        [],
    )
    browser = GuardedBrowser(SearchSite(always_empty=True), [ORIGIN], lambda *e: None)
    trace = await walk_flow(browser, candidate(), decide, nothing, 8)
    assert trace.status == "partial" and trace.fail_kind == "no_data"
    assert trace.data_recovery and trace.data_recovery.result == "still_empty"


# ── 통합 (실제 Playwright MCP) ──

needs_mcp = pytest.mark.skipif(
    not MCP_CLI.exists() or shutil.which("node") is None,
    reason="Playwright MCP 미설치 (npm install --prefix agent/mcp)",
)


@needs_mcp
def test_empty_archive_gets_synthetic_data(tmp_path: Path):
    server = start_site()
    site = f"http://127.0.0.1:{server.server_address[1]}"
    cfg = AgentConfig(
        log_dir=tmp_path / "logs",
        checkpoint_path=tmp_path / "cp.sqlite",
        output_root=tmp_path / "next-pjt",
        session_dir=tmp_path / "sessions",
        stub_step_ms=0,
        explorer={"mode": "mcp", "headless": True, "auth_headless": True, "walk_target": 6},
    )
    try:
        with TestClient(create_app(cfg, fake_llm=True)) as client:
            client.post("/query", json={"alias": "empty-t", "url": f"{site}/board.html"})
            deadline = time.monotonic() + 150
            while time.monotonic() < deadline:
                run = client.get("/runs/empty-t").json()
                if run["status"] in ("awaiting_analysis", "failed"):
                    break
                time.sleep(0.3)
    finally:
        server.shutdown()
    log = "\n".join(line["message"] for line in run["logs"])
    assert run["status"] == "awaiting_analysis", log[-1500:]

    store = CrawlStore(tmp_path / "next-pjt" / "empty-t" / "crawl")
    partial = [f for f in store.load_flows() if f.status == "partial"]
    assert partial, log[-1500:]
    archive_search = next(f for f in partial if "자료실" in f.name and f.kind == "search")
    recovery = archive_search.data_recovery
    assert recovery and recovery.result == "still_empty" and recovery.widened_steps
    assert recovery.fixture == f"fixtures/{recovery.empty_screen_id}.json"
    fixture = FixtureSet.model_validate_json((store.root / recovery.fixture).read_text("utf-8"))
    assert all(r.source == "synthetic" for r in fixture.records)
    assert [f.label for f in fixture.fields] == ["번호", "자료명", "등록자", "등록일", "파일 크기"]
    assert "부분 완주:" in log

    # 화면별 데이터 출처: 게시판은 observed, 빈 자료실은 synthetic (합성 데이터를 붙였으므로)
    sources = {s["title"]: s["dataSource"] for s in run["sitemap"]["screens"]}
    assert sources["공지사항 목록"] == "observed"
    assert sources["자료실"] == "synthetic"
    walk = {c["id"]: c for c in run["walk"]["candidates"]}
    assert walk[archive_search.flow_id]["status"] == "partial"
    assert walk[archive_search.flow_id]["fixture"] == recovery.fixture
