"""Explorer (T06 범위): 시작 화면을 열고 화면의 링크를 따라가 본다.

모든 이동은 GuardedBrowser를 거치므로 다른 origin 링크·외부 리다이렉트는 막히고 기록된다
(G2, EXP-02).
본격적인 사이트맵 수집(Map)·흐름 걷기(Walk)는 T07c·T07d에서 붙는다.
쓰기 동작 링크(로그아웃·삭제 등) 판정·승인은 T08(G1)에서 붙으므로
지금은 그런 이름의 링크를 건너뛴다.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from urllib.parse import urldefrag, urljoin, urlsplit

from .browser import BrowserActionError, GuardedBrowser, OriginBlockedError

# 스냅샷의 링크: - link "이름" [ref=e3] ...:\n    - /url: /page2.html
LINK_PATTERN = re.compile(r'link "(?P<name>[^"]*)"[^\n]*\n\s*- /url: (?P<url>\S+)')
# T08 전까지 따라가지 않는 위험 링크 이름 (GUARDRAILS.md G1 키워드)
RISKY_WORDS = ("로그아웃", "삭제", "탈퇴", "logout", "delete", "signout", "sign out")


@dataclass
class Link:
    name: str
    url: str


@dataclass
class VisitedPage:
    url: str
    title: str


@dataclass
class ExploreReport:
    pages: list[VisitedPage] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


class ExplorerError(RuntimeError):
    """수집을 이어 갈 수 없음 (시작 화면 접속 실패 등). 메시지는 콘솔에 그대로 보인다."""


class SessionExpiredError(RuntimeError):
    """수집 중 로그인 화면으로 되돌아감. 세션이 만료되었으므로 다시 인증해야 한다."""


def same_page(a: str | None, b: str | None) -> bool:
    """쿼리·앵커를 빼고 같은 주소인지."""
    if not a or not b:
        return False
    pa, pb = urlsplit(a), urlsplit(b)
    return (pa.scheme, pa.netloc, pa.path.rstrip("/")) == (
        pb.scheme,
        pb.netloc,
        pb.path.rstrip("/"),
    )


def parse_links(snapshot_text: str, base_url: str) -> list[Link]:
    """스냅샷에서 링크를 뽑아 절대 URL로 만든다 (중복·앵커 제거)."""
    links: list[Link] = []
    seen: set[str] = set()
    for m in LINK_PATTERN.finditer(snapshot_text):
        raw = m.group("url")
        if raw.startswith(("javascript:", "mailto:", "tel:")):
            continue
        url = urldefrag(urljoin(base_url, raw)).url
        if url not in seen:
            seen.add(url)
            links.append(Link(name=m.group("name"), url=url))
    return links


async def explore_links(
    browser: GuardedBrowser,
    start_url: str,
    max_links: int,
    log: Callable[[str], None],
    login_url: str | None = None,
    on_page: Callable[[VisitedPage], Awaitable[None]] | None = None,
) -> ExploreReport:
    """시작 화면 → 링크 하나씩 이동 → 돌아오기. 막힌 이동은 기록하고 계속한다.

    login_url을 주면, 로그인 화면이 아닌 곳으로 갔는데 로그인 화면에 닿을 때 세션 만료로 본다.
    on_page는 새 화면에 처음 도착할 때마다 그 화면이 열린 상태로 불린다 (원본 수집).
    """
    report = ExploreReport()

    def check_session(target: str, landed: str | None) -> None:
        if login_url and same_page(landed, login_url) and not same_page(target, login_url):
            raise SessionExpiredError(f"{target} 이동이 로그인 화면으로 되돌아갔습니다")

    try:
        first = await browser.call("browser_navigate", {"url": start_url})
    except BrowserActionError as e:
        raise ExplorerError(f"시작 화면을 열 수 없습니다: {start_url} ({e})") from e
    check_session(start_url, first.page_url)
    start_page = VisitedPage(url=first.page_url or start_url, title=first.page_title or "")
    report.pages.append(start_page)
    log(f"시작 화면: {first.page_title or ''} ({first.page_url or start_url})")
    if on_page:
        await on_page(start_page)

    snapshot = await browser.call("browser_snapshot", {})
    base = snapshot.page_url or start_url
    links = parse_links(snapshot.text, base)
    log(f"시작 화면 링크 {len(links)}개, 최대 {max_links}개까지 따라가 봅니다")

    for link in links[:max_links]:
        if any(w in link.name.lower() for w in RISKY_WORDS):
            report.skipped.append(link.url)
            log(f"위험 동작 링크는 건너뜀(T08에서 승인 처리): {link.name}")
            continue
        try:
            page = await browser.call("browser_navigate", {"url": link.url})
        except OriginBlockedError:
            report.blocked.append(link.url)
            continue
        except BrowserActionError as e:
            report.failed.append(link.url)
            log(f"화면을 열 수 없어 건너뜀: {link.url} ({e})")
            await browser.call("browser_navigate", {"url": base})
            continue
        check_session(link.url, page.page_url)
        visited = page.page_url or link.url
        if all(p.url != visited for p in report.pages):
            new_page = VisitedPage(url=visited, title=page.page_title or "")
            report.pages.append(new_page)
            log(f"화면 확인: {page.page_title or ''} ({visited})")
            if on_page:
                await on_page(new_page)
        try:
            await browser.call("browser_navigate", {"url": base})
        except OriginBlockedError:
            report.blocked.append(base)
    return report
