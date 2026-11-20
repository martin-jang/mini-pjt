"""화면 하나의 원본 수집 (T07b). 모든 도구 호출은 GuardedBrowser를 거친다.

원본은 마스킹을 거친 값만 저장한다. 지금은 계정·세션 값(G3·G10)을 가린다.
개인정보(G5, Presidio)·스크린샷 마스킹은 T09에서 이 단계에 붙는다.
"""

from __future__ import annotations

import base64
import re
from collections.abc import Callable

from .browser import GuardedBrowser, result_section
from .crawl import (
    NetworkLog,
    NetworkRequest,
    RawCapture,
    ScreenCapture,
    Viewport,
    now_iso,
    screen_id_for,
)

YAML_BLOCK = re.compile(r"```yaml\n(.*?)```", re.S)
# 1. [GET] http://host/path => [200] OK
REQUEST_LINE = re.compile(
    r"^\d+\.\s+\[(?P<method>[A-Z]+)\]\s+(?P<url>\S+)(?:\s+=>\s+\[(?P<status>\d+)\]\s*(?P<text>.*))?$",
    re.M,
)
VIEWPORT_ATTR = re.compile(r'data-l2n-viewport="(\d+),(\d+)"')


def parse_aria(snapshot_text: str) -> str:
    m = YAML_BLOCK.search(snapshot_text)
    return m.group(1) if m else ""


def parse_network(text: str) -> NetworkLog:
    requests = [
        NetworkRequest(
            method=m.group("method"),
            url=m.group("url"),
            status=int(m.group("status")) if m.group("status") else None,
            status_text=(m.group("text") or "").strip(),
        )
        for m in REQUEST_LINE.finditer(result_section(text))
    ]
    return NetworkLog(requests=requests)


async def capture_screen(
    browser: GuardedBrowser, url: str, title: str, mask: Callable[[str], str]
) -> RawCapture:
    """지금 열린 화면의 원본을 모은다: 접근성 스냅샷, 줄인 DOM, 네트워크, 콘솔, 스크린샷."""
    snapshot = await browser.call("browser_snapshot", {})
    dom = await browser.run_fixed_script("capture_dom")
    network = await browser.call("browser_network_requests", {"static": True})
    console = await browser.call("browser_console_messages", {"level": "info"})
    shot = await browser.call("browser_take_screenshot", {"type": "png"})

    page_url = snapshot.page_url or url
    dom_html = mask(str(dom))
    vp = VIEWPORT_ATTR.search(dom_html)
    capture = ScreenCapture(
        screen_id=screen_id_for(page_url),
        url=mask(page_url),
        title=mask(snapshot.page_title or title),
        captured_at=now_iso(),
        viewport=Viewport(width=int(vp.group(1)), height=int(vp.group(2))) if vp else None,
    )
    net = parse_network(network.text)
    for r in net.requests:
        r.url = mask(r.url)
    return RawCapture(
        capture=capture,
        screenshot_png=base64.b64decode(shot.images[0]) if shot.images else None,
        aria_yaml=mask(parse_aria(snapshot.text)),
        dom_html=dom_html,
        network=net,
        console_log=mask(result_section(console.text)),
    )
