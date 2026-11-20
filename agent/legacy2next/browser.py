"""Playwright MCP 연결과 가드 래퍼 (G1 허용 도구, G2 origin 검사).

`--allowed-origins`는 1차 방어일 뿐 보안 경계가 아니고 리다이렉트도 막지 않으므로,
도구 래퍼에서 이동 전 대상 URL과 이동 후 현재 URL을 다시 검사한다 (GUARDRAILS.md G2).
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Mapping, Sequence
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType, TracebackType
from typing import Any, Literal, Protocol

from mcp.client.stdio import stdio_client

from mcp import ClientSession, StdioServerParameters

from .config import AGENT_DIR, origin_of

logger = logging.getLogger(__name__)

MCP_CLI = AGENT_DIR / "mcp" / "node_modules" / "@playwright" / "mcp" / "cli.js"

# Explorer가 쓰는 도구만 허용한다: 이동·스냅샷·스크린샷·클릭·입력·네트워크 조회 (G1)
# 임의 JS 실행(browser_evaluate, browser_run_code_unsafe)과 파일 업로드는 쓰지 않는다
ALLOWED_TOOLS: frozenset[str] = frozenset(
    {
        "browser_navigate",
        "browser_navigate_back",
        "browser_snapshot",
        "browser_take_screenshot",
        "browser_click",
        "browser_type",
        "browser_select_option",
        "browser_press_key",
        "browser_wait_for",
        "browser_network_requests",
        "browser_console_messages",
        "browser_close",
    }
)
# G1 예외: 코드에 고정된 읽기 전용 추출 스크립트 (이름 → 함수 원문). 도구 래퍼만 실행하고,
# 호출하는 쪽은 이름만 고른다. browser_evaluate를 직접 부르는 것은 계속 막힌다
SCRIPTS_DIR = Path(__file__).resolve().parent / "scripts"
FIXED_SCRIPTS: Mapping[str, str] = MappingProxyType(
    {"capture_dom": (SCRIPTS_DIR / "capture_dom.js").read_text(encoding="utf-8").strip()}
)
RESULT_SECTION = re.compile(r"### Result\n(.*?)(?=\n### |\Z)", re.S)
# 도구 실행 뒤 페이지가 바뀔 수 있는 도구 (이동 후 검사 대상)
PAGE_CHANGING = frozenset(
    {
        "browser_navigate",
        "browser_navigate_back",
        "browser_click",
        "browser_type",
        "browser_select_option",
        "browser_press_key",
    }
)

PAGE_URL_LINE = re.compile(r"^- Page URL: (\S+)", re.M)
PAGE_TITLE_LINE = re.compile(r"^- Page Title: (.*)$", re.M)
SAFE_NON_HTTP = ("about:blank",)


class ToolNotAllowedError(RuntimeError):
    """허용 도구 목록 밖의 도구 (G1)."""


class OriginBlockedError(RuntimeError):
    """허용 origin 밖으로 이동하려 했거나 이동됨 (G2)."""


class BrowserActionError(RuntimeError):
    """도구 실행 실패 (접속 불가, 요소 없음 등). 가드레일 위반과 구분한다."""


@dataclass
class ToolResult:
    text: str
    page_url: str | None = None
    page_title: str | None = None
    is_error: bool = False
    images: list[str] = field(default_factory=list)  # base64


def parse_result(content: Sequence[Any], is_error: bool = False) -> ToolResult:
    texts = [getattr(c, "text", "") for c in content if getattr(c, "type", "") == "text"]
    images = [getattr(c, "data", "") for c in content if getattr(c, "type", "") == "image"]
    text = "\n".join(texts)
    url = PAGE_URL_LINE.search(text)
    title = PAGE_TITLE_LINE.search(text)
    return ToolResult(
        text=text,
        page_url=url.group(1) if url else None,
        page_title=title.group(1).strip() if title else None,
        is_error=is_error,
        images=images,
    )


def result_section(text: str) -> str:
    """도구 응답의 `### Result` 부분만 돌려준다 (없으면 빈 문자열)."""
    m = RESULT_SECTION.search(text)
    return m.group(1).strip() if m else ""


class ToolCaller(Protocol):
    async def call(self, name: str, arguments: dict[str, Any]) -> ToolResult: ...


class McpBrowser:
    """Playwright MCP 서버를 stdio로 띄우고 도구를 부른다 (검사 없음, GuardedBrowser가 감싼다)."""

    def __init__(
        self,
        allowed_origins: Sequence[str],
        output_dir: Path,
        *,
        headless: bool = True,
        secrets_file: Path | None = None,
        storage_state: Path | None = None,
        caps: Sequence[str] = (),
        extension: bool = False,
        cli_path: Path = MCP_CLI,
    ) -> None:
        self._allowed_origins = list(allowed_origins)
        self._output_dir = output_dir
        self._headless = headless
        self._secrets_file = secrets_file
        self._storage_state = storage_state
        self._caps = list(caps)
        self._extension = extension
        self._cli_path = cli_path
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self.tool_names: set[str] = set()

    def server_args(self) -> list[str]:
        # extension: 사용자가 이미 로그인한 Chrome에 붙는다 (프로필·세션은 사용자 브라우저 것)
        mode = ["--extension"] if self._extension else ["--isolated"]
        args = [
            str(self._cli_path),
            *mode,
            "--output-dir",
            str(self._output_dir),
            # 1차 방어: 허용 origin만 요청 (보안 경계 아님)
            "--allowed-origins",
            ";".join(self._allowed_origins),
        ]
        if self._headless and not self._extension:
            args.append("--headless")
        if self._secrets_file:
            args += ["--secrets", str(self._secrets_file)]
        if self._storage_state and not self._extension:
            args += ["--storage-state", str(self._storage_state)]
        if self._caps:
            args += ["--caps", ",".join(self._caps)]
        return args

    async def __aenter__(self) -> McpBrowser:
        if not self._cli_path.exists():
            raise RuntimeError(
                "Playwright MCP가 설치되지 않았습니다: npm install --prefix agent/mcp"
            )
        self._output_dir.mkdir(parents=True, exist_ok=True)
        stack = AsyncExitStack()
        try:
            params = StdioServerParameters(command="node", args=self.server_args())
            read, write = await stack.enter_async_context(stdio_client(params))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            tools = await session.list_tools()
        except BaseException:
            await stack.aclose()
            raise
        self.tool_names = {t.name for t in tools.tools}
        missing = (ALLOWED_TOOLS - {"browser_close"}) - self.tool_names
        if missing:
            logger.warning("Playwright MCP에 없는 도구: %s", sorted(missing))
        self._stack, self._session = stack, session
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._stack:
            await self._stack.aclose()
        self._stack = self._session = None

    async def call(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        if not self._session:
            raise RuntimeError("브라우저 세션이 열려 있지 않습니다.")
        result = await self._session.call_tool(name, arguments)
        return parse_result(result.content, bool(result.isError))


GuardEmit = Callable[[Literal["G1", "G2"], str, Literal["blocked", "skipped"], str], None]
"""(규칙, 상세, 처리, 로그 메시지) 를 받아 가드레일 이벤트를 남기는 함수."""


class GuardedBrowser:
    """Explorer는 이 래퍼로만 브라우저를 다룬다."""

    def __init__(
        self, browser: ToolCaller, allowed_origins: Sequence[str], emit: GuardEmit
    ) -> None:
        self._browser = browser
        self._allowed = {origin_of(o) for o in allowed_origins}
        self._emit = emit
        self.current_url: str | None = None
        self._last_allowed_url: str | None = None

    def is_allowed(self, url: str) -> bool:
        if url in SAFE_NON_HTTP:
            return True
        try:
            return origin_of(url) in self._allowed
        except ValueError:
            return False  # http(s)가 아닌 주소(chrome-error:// 등)는 허용 밖

    async def call(self, name: str, arguments: dict[str, Any] | None = None) -> ToolResult:
        args = dict(arguments or {})
        if name not in ALLOWED_TOOLS:
            self._emit(
                "G1", f"허용되지 않은 도구 {name}", "blocked", f"G1 허용 목록 밖 도구 차단: {name}"
            )
            raise ToolNotAllowedError(name)

        if name == "browser_navigate":
            target = str(args.get("url", ""))
            if not self.is_allowed(target):
                self._emit(
                    "G2",
                    f"허용 origin 밖 이동 시도: {target}",
                    "blocked",
                    f"G2 허용 origin 밖 이동 차단(이동 전): {target}",
                )
                raise OriginBlockedError(target)

        result = await self._browser.call(name, args)
        if result.is_error:
            # 접속 실패(DNS·연결 거부 등)는 G2 위반이 아니라 동작 실패다
            first = next((ln for ln in result.text.splitlines() if ln.startswith("Error")), "")
            raise BrowserActionError(first or f"{name} 실패")

        if name in PAGE_CHANGING:
            url = result.page_url
            if url is None:
                url = (await self._browser.call("browser_snapshot", {})).page_url
            if url and not self.is_allowed(url):
                await self._restore()
                self._emit(
                    "G2",
                    f"동작 후 허용 origin 밖 페이지: {url}",
                    "blocked",
                    f"G2 허용 origin 밖 페이지로 바뀌어 되돌림(이동 후): {url}",
                )
                raise OriginBlockedError(url)
            if url:
                self.current_url = url
                self._last_allowed_url = url
        return result

    async def settled_page(self, before_url: str | None) -> ToolResult:
        """동작 뒤 지금 화면을 다시 본다. 클릭 응답은 이동이 끝나기 전 화면일 수 있어서,
        주소가 그대로면 1초 기다렸다가 한 번 더 본다."""
        page = await self.call("browser_snapshot", {})
        if before_url and page.page_url == before_url:
            await self.call("browser_wait_for", {"time": 1})
            page = await self.call("browser_snapshot", {})
        return page

    async def run_fixed_script(self, name: str) -> Any:
        """고정 추출 스크립트를 실행해 결과(JSON 값)를 돌려준다 (G1 예외, 읽기 전용).

        스크립트 원문은 FIXED_SCRIPTS에서만 가져온다. 목록에 없는 이름은 G1 차단.
        """
        script = FIXED_SCRIPTS.get(name)
        if script is None:
            self._emit(
                "G1", f"등록되지 않은 스크립트 {name}", "blocked", f"G1 고정 스크립트 아님: {name}"
            )
            raise ToolNotAllowedError(name)
        result = await self._browser.call("browser_evaluate", {"function": script})
        if result.is_error:
            raise BrowserActionError(f"추출 스크립트 실패: {name}")
        return json.loads(result_section(result.text))

    async def _restore(self) -> None:
        """이전 화면으로 되돌린다. 그래도 밖이면 마지막 허용 URL로 이동한다."""
        back = await self._browser.call("browser_navigate_back", {})
        url = back.page_url or (await self._browser.call("browser_snapshot", {})).page_url
        if (not url or not self.is_allowed(url)) and self._last_allowed_url:
            back = await self._browser.call("browser_navigate", {"url": self._last_allowed_url})
            url = back.page_url
        self.current_url = url
