"""Explorer Map (T07c): 화면을 넓게 돌며 사이트맵(crawl/graph.json)을 만든다.

조회만 하고 화면마다 LLM을 부르지 않는다. 모든 이동은 GuardedBrowser를 거치므로 다른 origin
링크·외부 리다이렉트는 막히고 기록된다 (G2, EXP-02).

- 주소가 있는 링크: 너비 우선으로 따라간다 (화면 수·깊이·같은 형태 URL 수 상한)
- 주소가 없는 스크립트 메뉴(javascript:, #): 메뉴 영역(nav·header·aside)에 있는 것만 이름으로 찾아
  클릭한다. 본문의 스크립트 링크는 동작일 수 있어 따라가지 않고 T07d(Walk)에서 판단한다
- 위험 동작 이름(로그아웃·삭제 등) 링크는 T08(G1 승인) 전까지 건너뛴다
- 링크는 저장한 원본 dom.min.html에서 뽑으므로, 링크가 놓인 영역과 메뉴 트리를
  저장본으로 다시 볼 수 있다
"""

from __future__ import annotations

import re
from collections import Counter, deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import parse_qsl, urldefrag, urljoin, urlsplit

from .browser import BrowserActionError, GuardedBrowser, OriginBlockedError, ToolResult
from .crawl import (
    Components,
    EdgeStatus,
    GraphEdge,
    GraphNode,
    Layout,
    LinkArea,
    MenuItem,
    ScreenCapture,
    SiteGraph,
    now_iso,
    screen_id_for,
)
from .derive import extract_links, extract_menu, parse_dom
from .login import parse_elements

# T08 전까지 따라가지 않는 위험 링크 이름 (GUARDRAILS.md G1 키워드)
RISKY_WORDS = ("로그아웃", "삭제", "탈퇴", "logout", "delete", "signout", "sign out")
# 스크립트 메뉴를 클릭해도 되는 영역
CLICK_AREAS = {"nav", "header", "aside"}
NUMERIC = re.compile(r"^\d+$")


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


def url_pattern(url: str) -> str:
    """같은 형태 URL 묶음: 숫자 경로 조각은 {n}, 쿼리는 키만 남긴다 (게시글 상세 수십 개 방지)."""
    parts = urlsplit(url)
    path = "/".join("{n}" if NUMERIC.match(seg) else seg for seg in parts.path.split("/"))
    keys = sorted({k for k, _ in parse_qsl(parts.query, keep_blank_values=True)})
    return f"{parts.netloc}{path}" + (f"?{'&'.join(keys)}" if keys else "")


def is_risky(label: str) -> bool:
    lowered = label.lower()
    return any(w in lowered for w in RISKY_WORDS)


@dataclass
class MapLimits:
    max_screens: int = 40
    max_depth: int = 3
    max_per_pattern: int = 5


@dataclass
class ScreenResult:
    """화면 하나를 저장한 결과 (원본 DOM과 파생 요약)."""

    capture: ScreenCapture
    dom_html: str
    layout: Layout
    components: Components


CaptureFn = Callable[[str, str], Awaitable[ScreenResult | None]]


@dataclass
class _Visit:
    depth: int
    via: str  # link | click
    url: str | None = None  # via=link
    source_url: str | None = None  # via=click: 메뉴가 있던 화면
    label: str = ""


@dataclass
class _Outcome:
    status: EdgeStatus
    reason: str = ""
    target: str | None = None


async def map_site(
    browser: GuardedBrowser,
    start_url: str,
    limits: MapLimits,
    capture: CaptureFn,
    log: Callable[[str], None],
    *,
    login_url: str | None = None,
    on_progress: Callable[[SiteGraph], None] | None = None,
) -> SiteGraph:
    """시작 화면부터 너비 우선으로 돌며 화면을 저장하고 사이트맵을 만든다."""
    graph = SiteGraph(start_url=start_url, generated_at=now_iso())
    edges: list[GraphEdge] = []
    url_outcome: dict[str, _Outcome] = {}
    click_outcome: dict[str, _Outcome] = {}
    patterns: Counter[str] = Counter()
    queued: set[str] = {start_url}
    clicked: set[str] = set()
    node_ids: set[str] = set()
    queue: deque[_Visit] = deque([_Visit(depth=0, via="link", url=start_url, label="시작")])
    first = True

    def check_session(target: str | None, landed: str | None) -> None:
        if login_url and same_page(landed, login_url) and not same_page(target, login_url):
            raise SessionExpiredError(f"{target or '메뉴'} 이동이 로그인 화면으로 되돌아갔습니다")

    def record(visit: _Visit, outcome: _Outcome) -> None:
        if visit.via == "click":
            click_outcome[visit.label] = outcome
        elif visit.url:
            url_outcome[visit.url] = outcome

    async def click_menu(visit: _Visit) -> ToolResult | None:
        assert visit.source_url
        await browser.call("browser_navigate", {"url": visit.source_url})
        snapshot = await browser.call("browser_snapshot", {})
        ref = next(
            (
                r
                for r, e in parse_elements(snapshot.text).items()
                if e.role == "link" and e.name == visit.label
            ),
            None,
        )
        if ref is None:
            record(visit, _Outcome("failed", "메뉴를 화면에서 찾지 못함"))
            return None
        page = await browser.call("browser_click", {"target": ref, "element": visit.label})
        landed = page.page_url or (await browser.call("browser_snapshot", {})).page_url or ""
        if landed == visit.source_url:
            record(visit, _Outcome("skipped", "클릭해도 주소가 바뀌지 않음 (하위 메뉴 펼침 등)"))
            return None
        return ToolResult(text=page.text, page_url=landed, page_title=page.page_title)

    async def open_visit(visit: _Visit) -> ToolResult | None:
        """화면을 연다. 못 열면 결과를 기록하고 None."""
        try:
            if visit.via == "click":
                return await click_menu(visit)
            assert visit.url
            return await browser.call("browser_navigate", {"url": visit.url})
        except OriginBlockedError:
            record(visit, _Outcome("blocked", "허용 origin 밖 (G2)"))
        except BrowserActionError as e:
            if first:
                raise ExplorerError(f"시작 화면을 열 수 없습니다: {start_url} ({e})") from e
            record(visit, _Outcome("failed", str(e)[:200]))
            log(f"화면을 열 수 없어 건너뜀: {visit.url or visit.label} ({e})")
        return None

    while queue:
        visit = queue.popleft()
        if len(graph.nodes) >= limits.max_screens:
            graph.truncated = True
            for rest in (visit, *queue):
                record(rest, _Outcome("limit", f"화면 수 상한 {limits.max_screens}개"))
            break
        page = await open_visit(visit)
        first = False
        if page is None:
            continue
        landed = page.page_url or visit.url or ""
        check_session(visit.url, landed)
        if screen_id_for(landed) in node_ids:
            record(visit, _Outcome("duplicate", "이미 수집한 화면", screen_id_for(landed)))
            continue
        result = await capture(landed, page.page_title or "")
        if result is None:
            record(visit, _Outcome("failed", "화면 저장 실패"))
            continue
        screen_id = result.capture.screen_id
        node_ids.add(screen_id)
        record(visit, _Outcome("followed", target=screen_id))
        if landed != visit.url:
            url_outcome.setdefault(landed, _Outcome("followed", target=screen_id))
        graph.nodes.append(
            GraphNode(
                screen_id=screen_id,
                url=landed,
                title=result.capture.title,
                depth=visit.depth,
                pattern=url_pattern(landed),
                regions=[r.role for r in result.layout.regions],
                tables=len(result.components.tables),
                forms=len(result.components.forms),
                buttons=len(result.components.buttons),
            )
        )
        log(f"화면 확인: {result.capture.title} ({landed})")

        root = parse_dom(result.dom_html)
        if not graph.menu:
            graph.menu = extract_menu(root)
        for link in extract_links(root):
            area: LinkArea = link.area
            if link.kind == "none" or (link.kind == "script" and not link.label):
                continue
            if is_risky(link.label):
                edges.append(
                    _edge(screen_id, link.label, None, area, "skipped", "위험 동작 (T08 승인 후)")
                )
                continue
            if link.kind == "download":
                edges.append(
                    _edge(screen_id, link.label, link.href, area, "skipped", "파일 내려받기")
                )
                continue
            if link.kind == "script":
                if area not in CLICK_AREAS:
                    reason = "본문 스크립트 링크 (T07d에서 판단)"
                    edges.append(_edge(screen_id, link.label, None, area, "skipped", reason))
                    continue
                edges.append(_edge(screen_id, link.label, None, area, "followed", "", via="click"))
                if link.label not in clicked and visit.depth < limits.max_depth:
                    clicked.add(link.label)
                    queue.append(
                        _Visit(
                            depth=visit.depth + 1, via="click", source_url=landed, label=link.label
                        )
                    )
                continue
            target_url = urldefrag(urljoin(landed, link.href)).url
            edges.append(_edge(screen_id, link.label, target_url, area, "followed", ""))
            if target_url in queued:
                continue
            if visit.depth >= limits.max_depth:
                url_outcome.setdefault(
                    target_url, _Outcome("limit", f"깊이 상한 {limits.max_depth}")
                )
                continue
            pattern = url_pattern(target_url)
            if patterns[pattern] >= limits.max_per_pattern:
                reason = f"같은 형태 URL 상한 {limits.max_per_pattern}개"
                url_outcome.setdefault(target_url, _Outcome("limit", reason))
                continue
            patterns[pattern] += 1
            queued.add(target_url)
            queue.append(
                _Visit(depth=visit.depth + 1, via="link", url=target_url, label=link.label)
            )
        if on_progress:
            on_progress(graph)

    graph.edges = _resolve_edges(edges, url_outcome, click_outcome)
    _fill_menu(graph.menu, start_url, url_outcome, click_outcome)
    graph.generated_at = now_iso()
    return graph


def _edge(
    source: str,
    label: str,
    url: str | None,
    area: LinkArea,
    status: EdgeStatus,
    reason: str,
    via: str = "link",
) -> GraphEdge:
    return GraphEdge.model_validate(
        {
            "source": source,
            "label": label,
            "url": url,
            "area": area,
            "status": status,
            "reason": reason,
            "via": via,
        }
    )


def _resolve_edges(
    edges: list[GraphEdge], url_outcome: dict[str, _Outcome], click_outcome: dict[str, _Outcome]
) -> list[GraphEdge]:
    """따라간 링크의 결과(도착 화면·막힘·상한)를 엣지에 채우고, 같은 엣지는 하나로 합친다."""
    resolved: list[GraphEdge] = []
    seen: set[tuple[str, str | None, str]] = set()
    for e in edges:
        if e.status == "followed":
            outcome = (
                click_outcome.get(e.label) if e.via == "click" else url_outcome.get(e.url or "")
            )
            if outcome is None:
                e = e.model_copy(update={"status": "limit", "reason": "방문하지 않음 (상한)"})
            else:
                update = {
                    "status": outcome.status,
                    "reason": outcome.reason,
                    "target": outcome.target,
                }
                e = e.model_copy(update=update)
        key = (e.source, e.target or e.url, e.label)
        if key not in seen:
            seen.add(key)
            resolved.append(e)
    return resolved


def _fill_menu(
    items: list[MenuItem],
    base: str,
    url_outcome: dict[str, _Outcome],
    click_outcome: dict[str, _Outcome],
) -> None:
    """메뉴 항목마다 그 메뉴로 수집한 화면 ID를 채운다."""
    for item in items:
        href = (item.href or "").strip()
        if href and not href.lower().startswith("javascript:") and href != "#":
            outcome = url_outcome.get(urldefrag(urljoin(base, href)).url)
        else:
            outcome = click_outcome.get(item.label)
        item.screen_id = outcome.target if outcome else None
        _fill_menu(item.children, base, url_outcome, click_outcome)
