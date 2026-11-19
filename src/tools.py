"""에이전트 도구 모음: MCP 크롤러 클라이언트.

크롤러 도구는 mcp_server/crawler_server.py(fastmcp, stdio)를 langchain-mcp-adapters로 불러옵니다.
절단 3단계(MCP 생략)를 적용하면 같은 함수(src/crawler_core.py)를 직접 호출하면 됩니다.
"""

from __future__ import annotations

import sys
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient

from src.config import ROOT


def mcp_client() -> MultiServerMCPClient:
    """크롤러 MCP 서버 연결 정보를 담은 클라이언트를 만듭니다 (호출 시마다 서버를 stdio로 띄움)."""
    return MultiServerMCPClient({
        "crawler": {
            "command": sys.executable,
            "args": [str(ROOT / "mcp_server" / "crawler_server.py")],
            "transport": "stdio",
            "cwd": str(ROOT),
        }
    })


async def crawler_tools() -> list:
    """크롤러 MCP 도구 목록 (LangChain BaseTool)."""
    return await mcp_client().get_tools()


async def call_crawler(tool_name: str, **kwargs: Any) -> Any:
    """크롤러 MCP 도구 하나를 이름으로 호출합니다. 결과는 dict 또는 텍스트."""
    tools = {t.name: t for t in await crawler_tools()}
    if tool_name not in tools:
        return {"error": f"알 수 없는 크롤러 도구입니다: {tool_name}"}
    return await tools[tool_name].ainvoke(kwargs)
