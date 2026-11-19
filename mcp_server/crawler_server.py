"""ASIS 크롤러 MCP 서버 (fastmcp, stdio).

가드레일을 '도구 경계'에서 강제하기 위해 공식 Playwright MCP 대신 자체 서버를 둡니다
(README 핵심 의사결정 #2). 공식 서버는 클릭·폼 입력을 모두 열어 두지만, 이 서버는
읽기 전용 수집과 설정에 등록된 1회 제출만 노출합니다.

실행 (직접 확인용): python -m mcp_server.crawler_server
에이전트는 src/tools.py 의 MCP 클라이언트로 이 서버를 띄웁니다.
"""

from __future__ import annotations

import sys
from pathlib import Path

# 저장소 루트를 import 경로에 추가 (python mcp_server/crawler_server.py 로 띄워도 동작하도록)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastmcp import FastMCP  # noqa: E402

from src import crawler_core as cc  # noqa: E402

mcp = FastMCP("asis-crawler")


@mcp.tool
async def crawl_site(start_url: str, login_approved: bool = False) -> dict:
    """레거시 웹 시스템을 읽기 전용으로 크롤링해 화면 스냅샷을 저장합니다.

    언제 쓰나: 사용자가 URL 분석을 요청했을 때. 허용 도메인 안의 링크만 따라가며,
        같은 화면(쿼리 값만 다른 URL)은 한 번만 수집합니다.
    login_approved: 사용자가 데모 계정 로그인을 승인했으면 True. False면 공개 화면만 수집하고
        needs_approval 을 돌려줍니다.
    언제 쓰지 않나: 허용 목록 밖 도메인·내부망 주소 (자동 거부), 폼 제출이 필요한 경우.
    """
    try:
        return await cc.crawl_with_login(start_url, login_approved=login_approved)
    finally:
        await cc.SESSION.close()


@mcp.tool
async def capture_page(url: str) -> dict:
    """화면 1개의 구조(폼 필드·버튼·테이블·링크)를 수집합니다. 공개 화면 전용입니다.

    언제 쓰나: 특정 공개 화면만 다시 수집할 때.
    언제 쓰지 않나: 로그인이 필요한 화면 (crawl_site 를 login_approved=True 로 사용).
    """
    try:
        return cc.public_view(await cc.capture_page(url))
    finally:
        await cc.SESSION.close()


@mcp.tool
async def submit_once_and_capture(name: str, approved: bool = False) -> dict:
    """설정에 등록된 폼(예: 이체)을 1회만 제출하고 결과 화면을 수집합니다.

    언제 쓰나: 결과 화면은 읽기 전용으로 볼 수 없고, 사용자가 실행을 승인했을 때만.
    언제 쓰지 않나: 승인 전(needs_approval 반환), 설정에 없는 폼(거부), 이미 1회 실행한 경우(거부).
    """
    try:
        return await cc.submit_once_and_capture(name, approved=approved)
    finally:
        await cc.SESSION.close()


@mcp.tool
def list_snapshots() -> dict:
    """저장된 화면 스냅샷 목록(화면 ID, 제목, URL, 로그인 필요 여부)을 돌려줍니다.

    언제 쓰나: 이미 수집한 결과를 다시 확인할 때 (네트워크 접근 없음, 재생 모드에서도 사용).
    """
    snaps = cc.load_snapshots()
    return {"count": len(snaps), "screens": [
        {"screen_id": s["screen_id"], "title": s.get("title"), "url": s.get("url"),
         "requires_login": s.get("requires_login")} for s in snaps]}


if __name__ == "__main__":
    mcp.run(show_banner=False)
