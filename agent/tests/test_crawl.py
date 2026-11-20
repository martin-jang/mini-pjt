"""T07b 수집 데이터 구조.

단위: dom.min.html → layout·components·tokens 파생, 화면 ID, 저장소 경로 제한(G9), manifest 병합,
고정 추출 스크립트만 실행(G1 예외).
통합(실제 Playwright MCP + 시험 사이트): 수집한 화면마다 원본·파생 파일이 스키마대로 저장되고,
파생 파일을 지운 뒤 저장본만으로 똑같이 다시 만들어진다.
"""

import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from legacy2next.api import create_app
from legacy2next.browser import MCP_CLI, GuardedBrowser, ToolNotAllowedError, ToolResult
from legacy2next.capture import parse_network
from legacy2next.config import AgentConfig
from legacy2next.crawl import (
    DERIVED_FILES,
    RAW_FILES,
    Components,
    CrawlManifest,
    CrawlStore,
    Layout,
    NetworkLog,
    ScreenCapture,
    Tokens,
    main,
    screen_id_for,
)
from legacy2next.derive import derive_all

from .fixtures.site_server import start_site

S = 'data-l2n-style="c=rgb(51, 51, 51);bg=rgba(0, 0, 0, 0);ff=Dotum;fs=12;fw=400;p=0 0 0 0;m=0 0 0 0;br=0;d=block"'
BRAND = 'data-l2n-style="c=rgb(255, 255, 255);bg=rgb(200, 30, 30);ff=Dotum;fs=12;fw=700;p=4 8 4 8;m=0 0 0 0;br=3;d=inline-block"'
DOM = f"""<!doctype html><html data-l2n-url="https://a.example.com/list" data-l2n-viewport="1000,600"
data-l2n-page="1000,1200"><head><title>목록</title></head>
<body data-l2n-box="0,0,1000,1200" {S}>
<header data-l2n-box="0,0,1000,80" {S}>로고</header>
<div id="side" class="lnb" data-l2n-box="0,80,180,900" {S}><a href="/a" data-l2n-box="0,90,100,20" {S}>메뉴</a></div>
<div id="content" data-l2n-box="180,80,820,900" {S}>
<form method="POST" data-l2n-box="180,80,600,40" {S}>
<label for="q" data-l2n-box="0,0,1,1" {S}>검색어</label><input id="q" name="q" required pattern="[0-9]+" maxlength="10" data-l2n-box="0,0,1,1" {S}>
<label data-l2n-box="0,0,1,1" {S}>구분 <select name="kind" data-l2n-box="0,0,1,1" {S}><option {S}>전체</option><option {S}>일반</option></select></label>
<input type="submit" value="조회" data-l2n-box="0,0,1,1" {BRAND}>
</form>
<table data-l2n-box="180,130,800,200" {S}><tr {S}><th {S}>순번</th><th {S}>이름</th></tr>
<tr {S}><td {S}>1</td><td {S}>가</td></tr><tr {S}><td {S}>2</td><td {S}>나</td></tr></table>
<ul role="tablist" data-l2n-box="0,0,1,1" {S}><li {S}>탭1</li><li {S}>탭2</li></ul>
<div class="pagination" data-l2n-box="0,0,1,1" {S}><a {S}>1</a><a {S}>2</a><a {S}>다음</a></div>
<a role="button" data-l2n-box="0,0,1,1" {BRAND}>엑셀 다운로드</a>
</div>
<footer data-l2n-box="0,980,1000,60" {S}>ⓒ</footer>
</body></html>"""


def test_derive_from_dom_only():
    layout, comp, tokens = derive_all(DOM)
    assert [r.role for r in layout.regions] == ["header", "nav", "main", "footer"]
    assert layout.menu == "left"
    assert layout.viewport.width == 1000 and layout.page_height == 1200
    assert layout.density.interactive_per_screen == round(layout.density.interactive / 2, 1)

    assert comp.tables[0].headers == ["순번", "이름"] and comp.tables[0].rows == 2
    form = comp.forms[0]
    assert form.method == "post" and form.submits == ["조회"]
    q, kind = form.fields
    assert (q.label, q.required, q.pattern, q.max_length) == ("검색어", True, "[0-9]+", 10)
    assert (
        kind.label.startswith("구분") and kind.type == "select" and kind.options == ["전체", "일반"]
    )
    assert comp.tabs == [["탭1", "탭2"]]
    assert comp.paging[0].labels == ["1", "2", "다음"]
    assert "엑셀 다운로드" in comp.buttons

    assert tokens.accent_colors[0].value == "#c81e1e"  # 브랜드 색 (회색 아님)
    assert tokens.font_families[0].value == "Dotum"
    assert tokens.radius[0].value == "3px"
    # 같은 입력이면 같은 결과
    assert derive_all(DOM) == (layout, comp, tokens)


def test_screen_id_is_stable_and_safe():
    a = screen_id_for("https://a.example.com/board/list.do?menu=1")
    assert a == screen_id_for("https://a.example.com/board/list.do?menu=1#top")
    assert a != screen_id_for("https://a.example.com/board/list.do?menu=2")
    assert a.startswith("board-list-do-")
    assert screen_id_for("https://a.example.com/").startswith("home-")


def test_store_refuses_paths_outside_crawl(tmp_path: Path):
    store = CrawlStore(tmp_path / "crawl")
    for bad in ("../x", "a/b", "", "UPPER"):
        with pytest.raises(ValueError):
            store.screen_dir(bad)


def test_manifest_merges_screens(tmp_path: Path):
    store = CrawlStore(tmp_path / "crawl")

    def cap(sid: str, title: str) -> ScreenCapture:
        return ScreenCapture(screen_id=sid, url=f"https://a/{sid}", title=title, captured_at="t")

    store.update_manifest("site", [cap("a-1", "A"), cap("b-1", "B")])
    m = store.update_manifest("site", [cap("a-1", "A2")])
    assert [(s.screen_id, s.title) for s in m.screens] == [("a-1", "A2"), ("b-1", "B")]
    assert m.schema_version == 1


def test_parse_network_lines():
    text = (
        "### Result\n1. [GET] http://h/a => [200] OK\n2. [POST] http://h/api => [500] Error\n"
        "3. [GET] http://h/pending\n### Ran Playwright code"
    )
    log = parse_network(text)
    assert [(r.method, r.status) for r in log.requests] == [
        ("GET", 200),
        ("POST", 500),
        ("GET", None),
    ]


class Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def call(self, name: str, arguments: dict) -> ToolResult:
        self.calls.append((name, arguments))
        return ToolResult(text='### Result\n"<html></html>"')


async def test_only_fixed_scripts_can_run_g1():
    rec = Recorder()
    events: list[tuple] = []
    browser = GuardedBrowser(rec, ["https://a.example.com"], lambda *e: events.append(e))
    with pytest.raises(ToolNotAllowedError):
        await browser.call("browser_evaluate", {"function": "() => document.cookie"})
    with pytest.raises(ToolNotAllowedError):
        await browser.run_fixed_script("steal_cookie")
    assert rec.calls == [] and [e[0] for e in events] == ["G1", "G1"]

    assert await browser.run_fixed_script("capture_dom") == "<html></html>"
    name, args = rec.calls[0]
    assert name == "browser_evaluate" and "data-l2n-box" in args["function"]


# ── 통합 (실제 Playwright MCP) ─────────────────────────────

needs_mcp = pytest.mark.skipif(
    not MCP_CLI.exists() or shutil.which("node") is None,
    reason="Playwright MCP 미설치 (npm install --prefix agent/mcp)",
)


@needs_mcp
def test_collected_screens_are_saved_and_rederivable(tmp_path: Path):
    server = start_site()
    site = f"http://127.0.0.1:{server.server_address[1]}"
    cfg = AgentConfig(
        log_dir=tmp_path / "logs",
        checkpoint_path=tmp_path / "cp.sqlite",
        output_root=tmp_path / "next-pjt",
        session_dir=tmp_path / "sessions",
        stub_step_ms=0,
        explorer={"mode": "mcp", "headless": True, "auth_headless": True},
    )
    try:
        with TestClient(create_app(cfg, fake_llm=True)) as client:
            client.post("/query", json={"alias": "crawl-t", "url": f"{site}/"})
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                run = client.get("/runs/crawl-t").json()
                if run["status"] in ("awaiting_analysis", "failed"):
                    break
                time.sleep(0.3)
    finally:
        server.shutdown()
    assert run["status"] == "awaiting_analysis", run["logs"][-3:]
    log = "\n".join(line["message"] for line in run["logs"])
    assert "화면 저장: board-html-" in log

    crawl = tmp_path / "next-pjt" / "crawl-t" / "crawl"
    manifest = CrawlManifest.model_validate_json((crawl / "manifest.json").read_text("utf-8"))
    assert {s.title for s in manifest.screens} >= {"시험 사이트 홈", "공지 목록", "공지사항 목록"}
    assert all(s.url.startswith(site) for s in manifest.screens)  # 다른 origin 화면은 없다

    store = CrawlStore(crawl)
    before: dict[str, dict[str, bytes]] = {}
    for entry in manifest.screens:
        screen = crawl / "screens" / entry.screen_id
        for name in RAW_FILES:
            assert (screen / "raw" / name).exists(), f"{entry.screen_id}/raw/{name}"
        ScreenCapture.model_validate_json((screen / "raw" / "capture.json").read_text("utf-8"))
        NetworkLog.model_validate_json((screen / "raw" / "network.json").read_text("utf-8"))
        assert (screen / "raw" / "screenshot.png").read_bytes()[:4] == b"\x89PNG"
        derived = screen / "derived"
        Layout.model_validate_json((derived / "layout.json").read_text("utf-8"))
        Components.model_validate_json((derived / "components.json").read_text("utf-8"))
        Tokens.model_validate_json((derived / "tokens.json").read_text("utf-8"))
        before[entry.screen_id] = {n: (derived / n).read_bytes() for n in DERIVED_FILES}

    board = next(s for s in manifest.screens if s.title == "공지사항 목록")
    comp = Components.model_validate_json(
        (crawl / "screens" / board.screen_id / "derived" / "components.json").read_text("utf-8")
    )
    assert comp.tables[0].headers == ["번호", "제목", "작성자", "등록일"]
    assert [f.label for f in comp.forms[0].fields] == ["검색조건", "검색어", "등록일"]

    # 파생 파일을 모두 지우고 저장본만으로 다시 만든다 (브라우저 없이)
    for screen_id in before:
        shutil.rmtree(crawl / "screens" / screen_id / "derived")
    assert main([str(crawl)]) == 0
    for screen_id, files in before.items():
        derived = crawl / "screens" / screen_id / "derived"
        assert {n: (derived / n).read_bytes() for n in DERIVED_FILES} == files
    assert store.screen_ids() == sorted(before)
