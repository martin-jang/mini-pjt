"""T07c Map: 사이트맵(graph.json) 만들기.

가짜 브라우저로 규칙을 확인한다 (실제 MCP는 test_browser·test_crawl·E2E).
"""

from typing import Any

import pytest

from legacy2next.browser import GuardedBrowser, ToolResult
from legacy2next.crawl import Components, Layout, Region, ScreenCapture
from legacy2next.derive import extract_links, extract_menu, parse_dom
from legacy2next.explorer import (
    MapLimits,
    ScreenResult,
    SessionExpiredError,
    map_site,
    url_pattern,
)

ORIGIN = "https://legacy.example.com"
B = 'data-l2n-box="0,0,10,10"'

HOME = f"""<html data-l2n-viewport="1000,600" data-l2n-page="1000,600"><body {B}>
<div id="header" {B}><a href="/" {B}>로고</a><a href="/logout.do" {B}>로그아웃</a></div>
<div id="lnb" {B}><ul {B}>
  <li {B}><a href="/a" {B}>업무 A</a></li>
  <li {B}><a href="javascript:fnMenu('m2')" {B}>스크립트 메뉴</a>
    <ul {B}><li {B}><a href="/a/sub" {B}>하위 메뉴</a></li></ul></li>
</ul></div>
<div id="contents" {B}>
  {"".join(f'<a href="/view.do?id={i}" {B}>글 {i}</a>' for i in range(1, 8))}
  <a href="javascript:fnDetail(1)" {B}>상세보기</a>
  <a href="/files/manual.pdf" {B}>매뉴얼</a>
</div>
<div id="footer" {B}><a href="https://other.example.net/" {B}>외부 기관</a></div>
</body></html>"""
PAGE = f'<html><body {B}><div id="contents" {B}><a href="/" {B}>홈</a></div></body></html>'


def test_links_and_menu_come_from_saved_dom():
    root = parse_dom(HOME)
    links = {link.label: link for link in extract_links(root)}
    assert links["업무 A"].area == "nav" and links["업무 A"].kind == "url"
    assert links["스크립트 메뉴"].kind == "script"
    assert links["매뉴얼"].kind == "download"
    assert links["외부 기관"].area == "footer"
    menu = extract_menu(root)
    assert [m.label for m in menu] == ["업무 A", "스크립트 메뉴"]
    assert menu[1].children[0].label == "하위 메뉴"


def test_url_pattern_groups_detail_pages():
    assert url_pattern(f"{ORIGIN}/view.do?id=1") == url_pattern(f"{ORIGIN}/view.do?id=99")
    assert url_pattern(f"{ORIGIN}/board/12/view") == url_pattern(f"{ORIGIN}/board/7/view")
    assert url_pattern(f"{ORIGIN}/a") != url_pattern(f"{ORIGIN}/b")


class FakeSite:
    """URL로 이동하고, 스크립트 메뉴는 클릭하면 /js-menu로 간다."""

    def __init__(self, login_redirect: str | None = None) -> None:
        self.url = ""
        self.calls: list[str] = []
        self.login_redirect = login_redirect

    async def call(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        self.calls.append(name)
        if name == "browser_navigate":
            self.url = arguments["url"]
            if self.login_redirect and self.url.endswith(self.login_redirect):
                self.url = f"{ORIGIN}/login"
        elif name == "browser_click":
            self.url = f"{ORIGIN}/js-menu"
        text = '- link "스크립트 메뉴" [ref=e9]' if name == "browser_snapshot" else ""
        return ToolResult(text=text, page_url=self.url, page_title=self.url.rsplit("/", 1)[-1])


def make_capture(site: FakeSite):
    async def capture(url: str, title: str) -> ScreenResult:
        from legacy2next.crawl import screen_id_for

        html = HOME if url == f"{ORIGIN}/" else PAGE
        return ScreenResult(
            capture=ScreenCapture(
                screen_id=screen_id_for(url), url=url, title=title or "home", captured_at="t"
            ),
            dom_html=html,
            layout=Layout.model_validate(
                {
                    "viewport": {"width": 1000, "height": 600},
                    "page_height": 600,
                    "regions": [
                        Region.model_validate(
                            {
                                "role": "main",
                                "box": {"x": 0, "y": 0, "width": 1, "height": 1},
                                "selector": "div",
                            }
                        ).model_dump()
                    ],
                    "density": {
                        "elements": 1,
                        "interactive": 1,
                        "text_blocks": 1,
                        "interactive_per_screen": 1,
                    },
                }
            ),
            components=Components(),
        )

    return capture


async def test_map_builds_sitemap_with_reasons():
    site = FakeSite()
    events: list[tuple] = []
    browser = GuardedBrowser(site, [ORIGIN], lambda *e: events.append(e))
    logs: list[str] = []
    graph = await map_site(
        browser,
        f"{ORIGIN}/",
        MapLimits(max_screens=20, max_depth=2, max_per_pattern=5),
        make_capture(site),
        logs.append,
    )
    urls = {n.url for n in graph.nodes}
    assert {f"{ORIGIN}/", f"{ORIGIN}/a", f"{ORIGIN}/a/sub", f"{ORIGIN}/js-menu"} <= urls
    assert len([u for u in urls if "view.do" in u]) == 5  # 같은 형태 URL 상한
    assert all(u.startswith(ORIGIN) for u in urls)

    by_label = {e.label: e for e in graph.edges if e.source == graph.nodes[0].screen_id}
    assert by_label["외부 기관"].status == "blocked"  # G2 이동 전 차단
    assert by_label["로그아웃"].status == "skipped" and "T08" in by_label["로그아웃"].reason
    assert by_label["매뉴얼"].status == "skipped"
    assert by_label["상세보기"].status == "skipped"  # 본문 스크립트 링크는 클릭하지 않는다
    assert by_label["글 7"].status == "limit"
    assert by_label["스크립트 메뉴"].via == "click" and by_label["스크립트 메뉴"].target
    assert by_label["업무 A"].status == "followed"
    assert [e[0] for e in events] == ["G2"]

    menu = {m.label: m for m in graph.menu}
    assert menu["업무 A"].screen_id and menu["스크립트 메뉴"].screen_id
    assert menu["스크립트 메뉴"].children[0].screen_id  # 하위 메뉴도 수집한 화면과 연결
    assert graph.nodes[0].depth == 0 and not graph.truncated


async def test_map_stops_at_screen_limit():
    site = FakeSite()
    browser = GuardedBrowser(site, [ORIGIN], lambda *e: None)
    graph = await map_site(
        browser, f"{ORIGIN}/", MapLimits(max_screens=3), make_capture(site), lambda m: None
    )
    assert len(graph.nodes) == 3 and graph.truncated
    assert any(e.status == "limit" and "화면 수 상한" in e.reason for e in graph.edges)


async def test_map_detects_session_expiry():
    site = FakeSite(login_redirect="/a")
    browser = GuardedBrowser(site, [ORIGIN], lambda *e: None)
    with pytest.raises(SessionExpiredError):
        await map_site(
            browser,
            f"{ORIGIN}/",
            MapLimits(),
            make_capture(site),
            lambda m: None,
            login_url=f"{ORIGIN}/login",
        )
