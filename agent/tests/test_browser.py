import shutil
from typing import Any

import pytest

from legacy2next.browser import (
    MCP_CLI,
    GuardedBrowser,
    McpBrowser,
    OriginBlockedError,
    ToolNotAllowedError,
    ToolResult,
)
from legacy2next.capture import capture_screen
from legacy2next.crawl import CrawlStore
from legacy2next.explorer import ExplorerError, MapLimits, ScreenResult, map_site

from .fixtures.site_server import start_site


class ScriptedBrowser:
    """도구 이름별로 정해 둔 페이지 URL을 돌려주는 가짜 MCP."""

    def __init__(self, urls: dict[str, list[str]]) -> None:
        self.urls = urls
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        self.calls.append((name, arguments))
        queue = self.urls.get(name, [])
        url = queue.pop(0) if queue else arguments.get("url")
        return ToolResult(text="", page_url=url)


def make(fake: ScriptedBrowser) -> tuple[GuardedBrowser, list[tuple[str, ...]]]:
    events: list[tuple[str, ...]] = []
    browser = GuardedBrowser(fake, ["https://legacy.example.com"], lambda *e: events.append(e))
    return browser, events


async def test_disallowed_tool_is_blocked_g1():
    fake = ScriptedBrowser({})
    browser, events = make(fake)
    for tool in ("browser_evaluate", "browser_run_code_unsafe", "browser_file_upload"):
        with pytest.raises(ToolNotAllowedError):
            await browser.call(tool, {})
    assert fake.calls == []  # 실행하지 않는다
    assert [e[0] for e in events] == ["G1", "G1", "G1"]


async def test_navigate_to_other_origin_is_blocked_before_running_g2():
    fake = ScriptedBrowser({})
    browser, events = make(fake)
    with pytest.raises(OriginBlockedError):
        await browser.call("browser_navigate", {"url": "https://evil.example.net/"})
    assert fake.calls == []
    assert events[0][0] == "G2" and "이동 전" in events[0][3]


async def test_redirect_out_is_rolled_back_g2():
    fake = ScriptedBrowser(
        {
            "browser_navigate": ["https://legacy.example.com/", "https://evil.example.net/landing"],
            "browser_navigate_back": ["https://legacy.example.com/"],
        }
    )
    browser, events = make(fake)
    await browser.call("browser_navigate", {"url": "https://legacy.example.com/"})
    with pytest.raises(OriginBlockedError):
        await browser.call("browser_navigate", {"url": "https://legacy.example.com/go-out"})
    assert ("browser_navigate_back", {}) in fake.calls
    assert browser.current_url == "https://legacy.example.com/"
    assert events[-1][0] == "G2" and "이동 후" in events[-1][3]


# ── 실제 Playwright MCP + 시험 사이트 (EXP-02) ──

needs_mcp = pytest.mark.skipif(
    not MCP_CLI.exists() or shutil.which("node") is None,
    reason="Playwright MCP 미설치 (npm install --prefix agent/mcp)",
)


def real_capture(browser: GuardedBrowser, store: CrawlStore):
    async def capture(url: str, title: str) -> ScreenResult:
        raw = await capture_screen(browser, url, title, lambda s: s)
        store.save_raw(raw)
        layout, components, _ = store.derive(raw.capture.screen_id)
        return ScreenResult(raw.capture, raw.dom_html, layout, components)

    return capture


@needs_mcp
async def test_real_mcp_blocks_other_origin_links(tmp_path):
    server = start_site()
    port = server.server_address[1]
    origin = f"http://127.0.0.1:{port}"
    events: list[tuple[str, ...]] = []
    try:
        async with McpBrowser([origin], tmp_path / "mcp") as mcp:
            browser = GuardedBrowser(mcp, [origin], lambda *e: events.append(e))
            graph = await map_site(
                browser,
                f"{origin}/",
                MapLimits(max_screens=10),
                real_capture(browser, CrawlStore(tmp_path / "crawl")),
                lambda m: None,
            )
    finally:
        server.shutdown()

    visited = {n.url for n in graph.nodes}
    assert f"{origin}/" in visited and f"{origin}/page2.html" in visited
    assert all(u.startswith(origin) for u in visited)  # 다른 origin 화면을 연 적이 없다
    status = {(e.label, e.status) for e in graph.edges}
    assert ("외부 사이트", "blocked") in status  # 외부 링크 차단 (이동 전)
    assert ("외부로 가는 리다이렉트", "blocked") in status  # 외부 리다이렉트 차단 (이동 후)
    assert ("로그아웃", "skipped") in status  # 위험 링크는 건너뜀
    rules = [e[0] for e in events]
    assert rules.count("G2") >= 2
    assert any("이동 전" in e[3] for e in events) and any("이동 후" in e[3] for e in events)


@needs_mcp
async def test_real_mcp_unreachable_start_is_not_a_g2_violation(tmp_path):
    origin = "http://127.0.0.1:9"  # 아무도 듣지 않는 포트
    events: list[tuple[str, ...]] = []
    async with McpBrowser([origin], tmp_path / "mcp") as mcp:
        browser = GuardedBrowser(mcp, [origin], lambda *e: events.append(e))
        with pytest.raises(ExplorerError, match="시작 화면을 열 수 없습니다"):
            await map_site(
                browser,
                f"{origin}/",
                MapLimits(),
                real_capture(browser, CrawlStore(tmp_path / "crawl")),
                lambda m: None,
            )
    assert events == []  # 접속 실패는 가드레일 이벤트가 아니다
