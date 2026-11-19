"""크롤러 핵심 로직 (Playwright, 읽기 전용).

mcp_server/crawler_server.py가 이 함수들을 MCP 도구로 감쌉니다. 일정상 MCP를 생략하는 절단
3단계에서는 이 함수들을 LangChain 도구로 바로 노출하면 됩니다.

가드레일:
  - G1: 모든 URL은 접근 직전에 check_url 통과 필수
  - G2: GET 탐색만. 폼 제출은 login(승인 후)과 submit_once_and_capture(승인 후, 1회)만.
        GET만으로 상태를 바꾸는 링크(로그아웃·삭제 등)는 키워드로 건너뜀
  - G3: 저장·반환하는 모든 텍스트는 mask_pii 적용

사이트 고유 값(도메인·시작 URL·계정)은 모두 인자나 설정에서 받습니다. 이 파일에 하드코딩하지 않습니다.
"""

from __future__ import annotations

import json
import re
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlsplit, urlunsplit

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from src.config import path as cfg_path
from src.config import settings
from src.guardrails import check_url, mask_pii

# GET만으로도 상태를 바꿀 수 있는 링크 (어느 사이트에나 통하는 일반 키워드)
UNSAFE_LINK = re.compile(
    r"(log\s*-?\s*out|logoff|sign\s*-?\s*out|signoff|delete|remove|reset|clean|initiali[sz]e|shutdown|destroy)",
    re.IGNORECASE,
)
# HTML 화면이 아닌 리소스
NON_HTML = re.compile(r"(\?wsdl|_wadl)", re.IGNORECASE)
# 화면으로 볼 수 있는 경로 확장자 (확장자가 없으면 화면으로 간주)
SCREEN_EXT = {"", ".htm", ".html", ".jsp", ".php", ".asp", ".aspx", ".do", ".action"}
# 세션 ID 같은 경로 파라미터 (;jsessionid=..., ;sid=...)
PATH_PARAM = re.compile(r";[a-z_]*session[a-z_]*=[^/?#]*", re.IGNORECASE)


# ──────────────────────────────────────────────────────────────────
# URL 정규화
# ──────────────────────────────────────────────────────────────────


def clean_url(url: str) -> str:
    """세션 경로 파라미터(;jsessionid=...)와 #fragment를 제거한 URL.

    urlparse는 마지막 경로 조각의 ;파라미터를 path에서 떼어 내므로, 분리하지 않는 urlsplit을 씁니다.
    """
    p = urlsplit(url)
    return urlunsplit(p._replace(path=PATH_PARAM.sub("", p.path), fragment=""))


def url_pattern(url: str) -> str:
    """같은 화면을 하나로 묶기 위한 패턴. 쿼리 값 중 숫자/긴 값은 {value}로 치환합니다.

    예) /activity.htm?id=12345 와 /activity.htm?id=54321 → /activity.htm?id={value}
    """
    p = urlsplit(clean_url(url))
    query = sorted(
        # 숫자·긴 값·마스킹 표식([ACCOUNT] 등)은 같은 화면의 다른 데이터로 봅니다
        (k, "{value}" if re.fullmatch(r"[\d\-]+|.{12,}|\[[A-Z_]+\]", v or "") else v) for k, v in parse_qsl(p.query)
    )
    return urlunsplit(p._replace(scheme="", netloc=p.netloc.lower(), query=urlencode(query, safe="{}")))


def screen_id(pattern: str) -> str:
    """파일명·식별자로 쓸 화면 ID."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", pattern.split("//", 1)[-1]).strip("_").lower()
    return slug[:80] or "root"


# ──────────────────────────────────────────────────────────────────
# 화면 캡처
# ──────────────────────────────────────────────────────────────────

_EXTRACT_JS = r"""
() => {
  const txt = (el) => (el?.innerText || el?.value || el?.getAttribute?.('aria-label') || '').trim().replace(/\s+/g, ' ');
  const labelFor = (inp) => {
    if (inp.id) { const l = document.querySelector(`label[for="${inp.id}"]`); if (l) return txt(l); }
    const cell = inp.closest('td'); const prev = cell?.previousElementSibling; if (prev) return txt(prev);
    const lab = inp.closest('label'); if (lab) return txt(lab);
    // <label> 없이 입력란 앞에 텍스트만 있는 레거시 화면 대비: 바로 앞 형제 노드의 텍스트
    let n = inp.previousSibling, collected = '';
    for (let i = 0; n && i < 4 && !collected; i++, n = n.previousSibling) {
      collected = (n.nodeType === 3 ? n.textContent : (n.innerText || '')).trim().replace(/\s+/g, ' ');
    }
    if (collected) return collected.slice(-40);
    return inp.getAttribute('placeholder') || '';
  };
  const forms = Array.from(document.querySelectorAll('form')).map((f, i) => ({
    index: i, id: f.id || f.getAttribute('name') || null,
    action: f.getAttribute('action'), method: (f.getAttribute('method') || 'GET').toUpperCase(),
    fields: Array.from(f.querySelectorAll('input,select,textarea'))
      .filter(e => !['hidden'].includes(e.type))
      .map(e => ({ name: e.name || e.id || '', type: e.tagName === 'SELECT' ? 'select' : (e.type || e.tagName.toLowerCase()),
                   label: labelFor(e), required: !!e.required,
                   options: e.tagName === 'SELECT' ? Array.from(e.options).slice(0, 5).map(o => txt(o)) : undefined }))
      .filter(x => !['submit','button','image','reset'].includes(x.type)),
    buttons: Array.from(f.querySelectorAll('button,input[type=submit],input[type=button]')).map(b => txt(b)).filter(Boolean),
  }));
  // 폼 밖에 있는 입력 요소(스크립트로 제출하는 화면 대비)
  const looseFields = Array.from(document.querySelectorAll('input,select,textarea'))
    .filter(e => !e.closest('form') && e.type !== 'hidden')
    .map(e => ({ name: e.name || e.id || '', type: e.tagName === 'SELECT' ? 'select' : (e.type || ''), label: labelFor(e) }))
    .filter(x => !['submit','button','image','reset'].includes(x.type));
  const tables = Array.from(document.querySelectorAll('table')).map((t, i) => {
    const rows = Array.from(t.querySelectorAll('tr'));
    const headerRow = t.querySelector('thead tr') || rows[0];
    const headers = headerRow ? Array.from(headerRow.querySelectorAll('th,td')).map(c => txt(c)) : [];
    const body = rows.slice(1);
    return { index: i, id: t.id || null, headers, row_count: body.length,
             sample_rows: body.slice(0, 2).map(r => Array.from(r.querySelectorAll('td')).map(c => txt(c))) };
  }).filter(t => t.headers.length > 1 && t.headers.some(h => h));
  const links = Array.from(document.querySelectorAll('a[href]')).map(a => ({ text: txt(a), href: a.href }));
  const headings = Array.from(document.querySelectorAll('h1,h2,h3')).map(h => txt(h)).filter(Boolean);
  const main = document.querySelector('main,#rightPanel,#content,.content') || document.body;
  const buttons = Array.from(document.querySelectorAll('button,input[type=submit],input[type=button]'))
    .filter(b => !b.closest('form')).map(b => txt(b)).filter(Boolean);
  return { title: document.title, headings, forms, loose_fields: looseFields, tables, links, buttons,
           text: txt(main).slice(0, 3000) };
}
"""


# PII가 들어갈 수 없는 식별자 키는 마스킹하지 않습니다 (url_pattern은 쿼리 값이 이미 {value}로 치환됨)
_NO_MASK_KEYS = {"screen_id", "url_pattern", "captured_at", "requires_login"}


def _mask_obj(obj: Any) -> Any:
    """dict/list 안의 모든 문자열에 mask_pii를 적용합니다 (G3)."""
    if isinstance(obj, str):
        return mask_pii(obj)
    if isinstance(obj, list):
        return [_mask_obj(x) for x in obj]
    if isinstance(obj, dict):
        return {k: (v if k in _NO_MASK_KEYS else _mask_obj(v)) for k, v in obj.items()}
    return obj


async def capture(page: Page, *, requires_login: bool) -> dict[str, Any]:
    """현재 페이지를 구조화된 스냅샷 dict로 만듭니다 (마스킹 적용)."""
    raw = await page.evaluate(_EXTRACT_JS)
    pattern = url_pattern(page.url)
    snap = {
        "screen_id": screen_id(pattern),
        "url": clean_url(page.url),
        "url_pattern": pattern,
        "requires_login": requires_login,
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        **raw,
    }
    raw_links = [l["href"] for l in raw.get("links", [])]
    masked = _mask_obj(snap)
    # 크롤링(다음 링크 따라가기)에는 마스킹 전 원본 링크가 필요합니다. 저장하지 않는 내부 키로만 보관합니다.
    masked["_raw_links"] = raw_links
    return masked


# ──────────────────────────────────────────────────────────────────
# 세션 (브라우저 1개를 유지해 로그인 상태를 이어갑니다)
# ──────────────────────────────────────────────────────────────────


@dataclass
class CrawlSession:
    browser: Browser | None = None
    context: BrowserContext | None = None
    logged_in: bool = False
    submitted_once: bool = False
    _pw: Any = None
    log: list[str] = field(default_factory=list)

    async def page(self) -> Page:
        if self.context is None:
            self._pw = await async_playwright().start()
            self.browser = await self._pw.chromium.launch()
            self.context = await self.browser.new_context()
            # G1: 페이지 안에서 발생하는 모든 요청(리다이렉트·리소스 포함)도 허용 도메인만 통과
            await self.context.route("**/*", self._route_guard)
        return await self.context.new_page()

    async def _route_guard(self, route, request) -> None:
        ok, _ = check_url(request.url, resolve_dns=False)
        if ok:
            await route.continue_()
        else:
            await route.abort()

    async def close(self) -> None:
        if self.browser:
            await self.browser.close()
        if self._pw:
            await self._pw.stop()
        self.browser = self.context = self._pw = None
        self.logged_in = False


SESSION = CrawlSession()


def _timeout() -> int:
    return int(settings()["crawl"]["timeout_ms"])


def _snapshot_dir(url: str) -> Path:
    return cfg_path("snapshots") / (urlparse(url).hostname or "unknown")


def save_snapshot(snap: dict[str, Any]) -> Path:
    """스냅샷 1개를 data/snapshots/{도메인}/{screen_id}.json 으로 저장합니다."""
    d = _snapshot_dir(snap["url"])
    d.mkdir(parents=True, exist_ok=True)
    out = d / f"{snap['screen_id']}.json"
    public = {k: v for k, v in snap.items() if not k.startswith("_")}  # 원본 링크 등 내부 키는 저장하지 않음
    if out.exists():
        prev = json.loads(out.read_text(encoding="utf-8"))
        # 비로그인으로 이미 수집한 공개 화면은 로그인 후 버전으로 덮어쓰지 않습니다.
        # (로그인하면 로그인 폼이 사라지는 등 공개 화면의 원래 구조가 바뀌기 때문)
        if not prev.get("requires_login") and public.get("requires_login"):
            return out
    out.write_text(json.dumps(public, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def load_snapshots(domain: str | None = None) -> list[dict[str, Any]]:
    """저장된 스냅샷 전체를 읽습니다 (재생 모드·분석용)."""
    root = cfg_path("snapshots")
    dirs = [root / domain] if domain else [p for p in root.glob("*") if p.is_dir()]
    snaps = []
    for d in dirs:
        for f in sorted(d.glob("*.json")):
            if f.name.startswith("_"):
                continue
            snaps.append(json.loads(f.read_text(encoding="utf-8")))
    return snaps


# ──────────────────────────────────────────────────────────────────
# 도구 본체
# ──────────────────────────────────────────────────────────────────


def public_view(snap: dict[str, Any]) -> dict[str, Any]:
    """내부 키(_로 시작)를 뺀 스냅샷. 도구 결과로 LLM·사용자에게 돌려줄 때 사용합니다."""
    return {k: v for k, v in snap.items() if not k.startswith("_")}


def _is_followable(href: str, base_host: str) -> bool:
    if not href or href.startswith(("javascript:", "mailto:", "tel:")):
        return False
    if NON_HTML.search(href) or UNSAFE_LINK.search(href):
        return False
    if Path(urlsplit(href).path).suffix.lower() not in SCREEN_EXT:
        return False
    return (urlparse(href).hostname or "").lower() == base_host


async def capture_page(url: str) -> dict[str, Any]:
    """URL 하나를 열어 스냅샷을 만들고 저장합니다. 거부되면 {'error': 사유}."""
    ok, reason = check_url(url)
    if not ok:
        return {"error": reason}
    page = await SESSION.page()
    try:
        resp = await page.goto(url, timeout=_timeout(), wait_until="domcontentloaded")
        try:  # 표·목록을 스크립트로 늦게 그리는 화면 대비 (실패해도 진행)
            await page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        if resp is not None and "html" not in (resp.headers.get("content-type") or "html"):
            return {"error": f"HTML 화면이 아니라 수집하지 않았습니다 ({url})."}
        snap = await capture(page, requires_login=SESSION.logged_in)
        save_snapshot(snap)
        return snap  # 내부 키(_raw_links) 포함. 외부로 돌려줄 때는 public_view 사용
    except Exception as e:  # 네트워크 오류는 안내 문자열로 돌려줍니다
        return {"error": f"화면을 열 수 없습니다 ({url}): {type(e).__name__}"}
    finally:
        await page.close()


async def crawl_site(start_url: str, max_depth: int | None = None, max_pages: int | None = None) -> dict[str, Any]:
    """시작 URL부터 같은 도메인 링크를 BFS로 따라가며 화면을 수집합니다 (읽기 전용).

    같은 url_pattern은 한 번만 수집합니다 (계좌번호만 다른 상세 화면 중복 방지).
    """
    ok, reason = check_url(start_url)
    if not ok:
        return {"error": reason, "screens": []}
    crawl_cfg = settings()["crawl"]
    max_depth = crawl_cfg["max_depth"] if max_depth is None else max_depth
    max_pages = crawl_cfg["max_pages"] if max_pages is None else max_pages
    host = (urlparse(start_url).hostname or "").lower()

    seen: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(start_url, 0)])
    screens, skipped = [], []
    while queue and len(screens) < max_pages:
        url, depth = queue.popleft()
        pat = url_pattern(url)
        if pat in seen:
            continue
        seen.add(pat)
        snap = await capture_page(url)
        if "error" in snap:
            skipped.append(snap["error"])
            continue
        screens.append({"screen_id": snap["screen_id"], "url": snap["url"], "title": snap["title"]})
        if depth < max_depth:
            for raw_href in snap.get("_raw_links", []):
                href = clean_url(urljoin(url, raw_href))
                if _is_followable(href, host) and url_pattern(href) not in seen:
                    queue.append((href, depth + 1))
    return {"screens": screens, "skipped": skipped[:20], "logged_in": SESSION.logged_in}


def _submit_flag(host: str) -> Path:
    return cfg_path("snapshots") / host / "_submitted_once.json"


async def submit_once_and_capture(name: str, approved: bool) -> dict[str, Any]:
    """설정(submit_once)에 등록된 폼을 1회만 제출하고 결과 화면을 수집합니다 (G2 유일한 예외, H2).

    언제 쓰나: 결과 화면을 읽기 전용으로는 볼 수 없고, 사용자가 HITL에서 실행을 승인했을 때.
    언제 쓰지 않나: 승인 전, 설정에 없는 폼, 이미 한 번 실행한 경우 → 실행하지 않고 사유를 돌려줍니다.
    로그인이 필요하면 내부에서 데모 계정으로 로그인합니다 (stdio MCP는 호출 간 세션이 유지되지 않음).
    """
    from src.config import demo_credentials

    target = settings()["target"]
    spec = next((s for s in target.get("submit_once", []) if s["name"] == name), None)
    if spec is None:
        return {"error": f"거부: 1회 제출이 허용된 폼이 아닙니다 ({name}). 읽기 전용 정책상 실행하지 않습니다."}
    if not approved:
        return {"needs_approval": True, "reason": f"'{name}' 폼을 1회 제출합니다. 실행 전 승인이 필요합니다.",
                "form": spec["form_id"], "values": spec["values"]}
    start = target["start_url"]
    host = (urlparse(start).hostname or "").lower()
    flag = _submit_flag(host)
    if flag.exists():
        return {"error": "거부: 이 폼은 이미 1회 제출했습니다. 저장된 결과 화면을 사용하세요."}
    page_url = urljoin(start, spec["page_path"])
    ok, reason = check_url(page_url)
    if not ok:
        return {"error": reason}
    if not SESSION.logged_in:
        u, p = demo_credentials()
        lg = await login_with_demo_account(start, u or "", p or "", approved=True)
        if not lg.get("logged_in"):
            return {"error": lg.get("error", "로그인 실패")}
    page = await SESSION.page()
    try:
        await page.goto(page_url, timeout=_timeout())
        await page.wait_for_load_state("networkidle", timeout=10000)
        form = page.locator(f"form#{spec['form_id']}")
        for field_name, value in spec["values"].items():
            el = form.locator(f"[name='{field_name}'], #{field_name}").first
            if isinstance(value, dict) and "option_index" in value:
                await el.select_option(index=int(value["option_index"]))
            else:
                await el.fill(str(value))
        before = await page.evaluate("() => document.body.innerText")
        await form.locator("input[type=submit],button[type=submit],button").first.click()
        await page.wait_for_load_state("networkidle", timeout=10000)
        # 결과를 스크립트로 같은 화면에 그리는 경우 대비: 화면 텍스트가 바뀔 때까지 최대 10초 대기
        try:
            await page.wait_for_function("(b) => document.body.innerText !== b", arg=before, timeout=10000)
            await page.wait_for_timeout(1000)
        except Exception:
            pass
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.write_text(json.dumps({"name": name, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}), encoding="utf-8")
        snap = await capture(page, requires_login=True)
        # 같은 URL에서 결과가 표시되는 화면도 있으므로 결과 화면은 별도 ID로 저장
        snap["screen_id"] = f"{snap['screen_id']}__result"
        snap["url_pattern"] = f"{snap['url_pattern']}#result"
        snap["result_of"] = name
        save_snapshot(snap)
        return public_view(snap)
    except Exception as e:
        return {"error": f"제출 중 오류: {type(e).__name__}"}
    finally:
        await page.close()


async def crawl_with_login(start_url: str, login_approved: bool, max_depth: int | None = None,
                           max_pages: int | None = None) -> dict[str, Any]:
    """공개 화면 수집 → (승인 시) 로그인 → 로그인 후 화면 수집을 한 번의 호출로 수행합니다.

    stdio MCP는 호출마다 서버 프로세스가 새로 뜰 수 있어 로그인 상태가 이어지지 않으므로,
    로그인이 필요한 수집은 이 함수 하나로 끝냅니다.
    """
    from src.config import demo_credentials

    public = await crawl_site(start_url, max_depth=1, max_pages=max_pages)
    if "error" in public:
        return public
    result: dict[str, Any] = {"public_screens": public["screens"], "private_screens": [], "logged_in": False}
    if not login_approved:
        result["needs_approval"] = True
        result["reason"] = "로그인 후 화면을 수집하려면 데모 계정 로그인 승인이 필요합니다."
        return result
    u, p = demo_credentials()
    lg = await login_with_demo_account(start_url, u or "", p or "", approved=True)
    if not lg.get("logged_in"):
        result["error"] = lg.get("error")
        return result
    private = await crawl_site(lg["landing_url"], max_depth=max_depth, max_pages=max_pages)
    result.update(private_screens=private.get("screens", []), logged_in=True, skipped=private.get("skipped", []))
    return result


async def login_with_demo_account(login_url: str, username: str, password: str, approved: bool) -> dict[str, Any]:
    """데모 계정으로 로그인합니다 (H1). approved=True 일 때만 실행합니다.

    언제 쓰나: 사용자가 HITL에서 로그인을 승인한 뒤, 로그인 후 화면을 수집해야 할 때.
    언제 쓰지 않나: 승인 전. 승인이 없으면 실행하지 않고 needs_approval 안내를 돌려줍니다.
    로그인 폼은 비밀번호 입력란이 있는 첫 번째 폼으로 찾습니다 (사이트별 선택자 하드코딩 없음).
    """
    if not approved:
        return {"needs_approval": True, "reason": "데모 계정 로그인은 사용자 승인이 필요합니다."}
    if not username or not password:
        return {"error": "데모 계정이 설정되지 않았습니다 (.env 확인)."}
    ok, reason = check_url(login_url)
    if not ok:
        return {"error": reason}
    page = await SESSION.page()
    try:
        await page.goto(login_url, timeout=_timeout())
        pw = page.locator("input[type=password]").first
        form = pw.locator("xpath=ancestor::form")
        await form.locator("input[type=text],input[type=email],input:not([type])").first.fill(username)
        await pw.fill(password)
        await form.locator("input[type=submit],button[type=submit],button").first.click()
        await page.wait_for_load_state("domcontentloaded")
        still_login = await page.locator("input[type=password]").count() > 0
        SESSION.logged_in = not still_login
        if not SESSION.logged_in:
            return {"error": "로그인에 실패했습니다 (계정 또는 화면 구조 확인)."}
        return {"logged_in": True, "landing_url": clean_url(page.url)}
    except Exception as e:
        return {"error": f"로그인 중 오류: {type(e).__name__}"}
    finally:
        await page.close()
