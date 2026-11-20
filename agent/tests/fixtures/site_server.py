"""Explorer 검증용 시험 사이트.

- `/`: G2 검증. 내부 링크, 다른 origin 링크, 다른 origin으로 가는 리다이렉트, 로그아웃 링크
- `/board.html`: 수집 데이터 구조 검증 (T07b). 머리글·왼쪽 메뉴·검색 폼·표·탭·페이징·바닥글과
  브랜드 색이 있는 전형적인 레거시 목록 화면
- `/idpw/`: ID/PW 로그인이 필요한 영역 (T07a). 로그인하지 않으면 `/idpw/login`으로 보낸다
- `/cert/`: 간편인증(사람이 해야 하는 인증)이 필요한 영역 (T07a). 로그인 화면은 인증 승인을
  기다리며 `/cert/status`를 확인하고, 승인되면 세션 쿠키를 받는다.
  사용자가 휴대폰에서 승인하는 동작은 `POST /_test/approve`로 흉내 낸다
- `POST /_test/expire`: 발급한 세션을 모두 무효로 만든다 (세션 만료 흉내)

pytest에서는 start_site()로 스레드에서 띄우고, E2E에서는 스크립트로 띄운다:
    python tests/fixtures/site_server.py --port 8766
다른 origin은 같은 포트의 localhost(127.0.0.1과 origin이 다름)를 쓴다.
실제 외부 요청은 나가지 않는다.
"""

from __future__ import annotations

import argparse
import secrets
import threading
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

FIXTURE_USERNAME = "tester"
FIXTURE_PASSWORD = "fixture-pass-1234"


def _page(title: str, body: str) -> bytes:
    return (
        f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>{title}</title></head>'
        f"<body><h1>{title}</h1>{body}</body></html>"
    ).encode()


LOGIN_FORM = _page(
    "로그인",
    (
        '<form method="post" action="/idpw/login">'
        '<label>아이디 <input name="uid" type="text"></label> '
        '<label>비밀번호 <input name="upw" type="password"></label> '
        '<button type="submit">로그인</button></form>'
    ),
)

BOARD = (
    """<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>공지사항 목록</title>
<style>
body { margin: 0; font-family: "Malgun Gothic", sans-serif; font-size: 13px; color: #333333; }
#header { background: #1f4e8c; color: #ffffff; height: 60px; padding: 0 20px; }
#header .gnb a { color: #ffffff; margin-right: 16px; font-weight: 700; }
#wrap { display: flex; }
#lnb { width: 200px; min-height: 500px; background: #f2f5fa; padding: 12px; }
#lnb li { padding: 6px 0; }
#contents { flex: 1; padding: 20px; }
.tab { display: flex; gap: 4px; padding: 0; list-style: none; }
.tab li { padding: 6px 12px; border: 1px solid #cccccc; border-radius: 4px 4px 0 0; }
.btn { background: #1f4e8c; color: #ffffff; border: 0; padding: 4px 12px; border-radius: 3px; }
table { border-collapse: collapse; width: 100%; margin-top: 12px; }
th { background: #e9eef6; padding: 8px; border-top: 2px solid #1f4e8c; }
td { padding: 8px; border-bottom: 1px solid #dddddd; }
.paging { text-align: center; margin-top: 12px; }
.paging a, .paging strong { margin: 0 4px; }
#footer { background: #444444; color: #cccccc; padding: 16px 20px; font-size: 12px; }
</style></head><body>
<div id="header"><h1>시험 기관 업무시스템</h1>
<div class="gnb"><a href="/board.html">게시판</a><a href="/page2.html">공지</a></div></div>
<div id="wrap">
<div id="lnb"><ul><li><a href="/board.html">공지사항</a></li>
<li><a href="/page2.html">자료실</a></li></ul></div>
<div id="contents">
<h2>공지사항</h2>
<ul class="tab"><li>전체</li><li>일반</li><li>긴급</li></ul>
<form method="get" action="/board.html">
<label for="searchCnd">검색조건</label>
<select id="searchCnd" name="searchCnd"><option>제목</option><option>내용</option></select>
<label for="searchWrd">검색어</label>
<input id="searchWrd" name="searchWrd" type="text" required maxlength="50">
<label>등록일 <input name="regDate" type="date"></label>
<input type="submit" class="btn" value="조회">
</form>
<table><thead><tr><th>번호</th><th>제목</th><th>작성자</th><th>등록일</th></tr></thead>
<tbody>
<tr><td>3</td><td>시스템 점검 안내</td><td>관리자</td><td>2026-11-01</td></tr>
<tr><td>2</td><td>개인정보 처리방침 변경</td><td>관리자</td><td>2026-10-15</td></tr>
<tr><td>1</td><td>홈페이지 개설</td><td>관리자</td><td>2026-09-01</td></tr>
</tbody></table>
<div class="paging"><a href="#">처음</a><strong>1</strong>
<a href="#">2</a><a href="#">3</a><a href="#">다음</a></div>
<button type="button" class="btn">등록</button>
</div></div>
<div id="footer">Copyright 시험 기관. All rights reserved.</div>
<script>console.log("board loaded")</script>
</body></html>"""
).encode()

CERT_LOGIN = _page(
    "인증 로그인",
    (
        "<p>공동인증서 또는 간편인증(카카오·PASS)으로 로그인하세요.</p>"
        '<button type="button">공동인증서 로그인</button> '
        '<button type="button">간편인증 요청</button>'
        '<p id="state">휴대폰에서 인증을 승인해 주세요</p>'
        # 콘솔에서 손으로 확인할 때 휴대폰 승인 대신 누르는 버튼 (사람만 누른다)
        "<button type=\"button\" onclick=\"fetch('/_test/approve', {method: 'POST'})\">"
        "(시험용) 휴대폰에서 승인</button>"
        "<script>setInterval(async () => {"
        " const r = await fetch('/cert/status');"
        " if ((await r.text()) === 'ok') location.href = '/cert/home';"
        "}, 300);</script>"
    ),
)


class SiteState:
    """발급한 세션과 간편인증 승인 여부. 서버 인스턴스마다 따로 둔다."""

    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password
        self.sessions: set[str] = set()
        self.approved = False
        self.lock = threading.Lock()

    def issue(self) -> str:
        sid = secrets.token_hex(16)
        with self.lock:
            self.sessions.add(sid)
        return sid


class Handler(BaseHTTPRequestHandler):
    server: SiteServer

    def _send(
        self,
        status: int,
        body: bytes = b"",
        location: str | None = None,
        cookie: str | None = None,
        content_type: str = "text/html; charset=utf-8",
    ) -> None:
        self.send_response(status)
        if location:
            self.send_header("Location", location)
        if cookie:
            self.send_header("Set-Cookie", f"{cookie}; Path=/; HttpOnly")
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _logged_in(self, name: str) -> bool:
        jar = SimpleCookie(self.headers.get("Cookie", ""))
        sid = jar[name].value if name in jar else ""
        with self.server.state.lock:
            return sid in self.server.state.sessions

    def do_GET(self) -> None:  # noqa: N802 (http.server 규칙)
        port = self.server.server_address[1]
        external = f"http://localhost:{port}"
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self._send(
                200,
                _page(
                    "시험 사이트 홈",
                    (
                        '<a href="/page2.html">공지 목록</a> '
                        '<a href="/board.html">게시판</a> '
                        f'<a href="{external}/external.html">외부 사이트</a> '
                        '<a href="/go-out">외부로 가는 리다이렉트</a> '
                        '<a href="/logout">로그아웃</a>'
                    ),
                ),
            )
        elif path == "/board.html":
            self._send(200, BOARD)
        elif path == "/page2.html":
            self._send(200, _page("공지 목록", '<a href="/">홈</a>'))
        elif path == "/go-out":
            self._send(302, location=f"{external}/external.html")
        elif path == "/external.html":
            self._send(200, _page("외부 페이지", "여기에 오면 안 된다"))
        elif path == "/idpw/login":
            self._send(200, LOGIN_FORM)
        elif path.startswith("/idpw/"):
            if not self._logged_in("idpw_sid"):
                self._send(302, location="/idpw/login")
            elif path in ("/idpw/", "/idpw/home"):
                self._send(
                    200,
                    _page(
                        "업무 홈",
                        '<a href="/idpw/notice">공지사항</a> <a href="/idpw/members">회원 목록</a>',
                    ),
                )
            elif path == "/idpw/notice":
                self._send(200, _page("공지사항", '<a href="/idpw/home">홈</a>'))
            elif path == "/idpw/members":
                self._send(200, _page("회원 목록", '<a href="/idpw/home">홈</a>'))
            else:
                self._send(404, _page("없음", ""))
        elif path == "/cert/login":
            self._send(200, CERT_LOGIN)
        elif path == "/cert/status":
            with self.server.state.lock:
                approved = self.server.state.approved
            if approved:
                sid = self.server.state.issue()
                self._send(200, b"ok", cookie=f"cert_sid={sid}", content_type="text/plain")
            else:
                self._send(200, b"wait", content_type="text/plain")
        elif path.startswith("/cert/"):
            if not self._logged_in("cert_sid"):
                self._send(302, location="/cert/login")
            elif path in ("/cert/", "/cert/home"):
                self._send(200, _page("민원 홈", '<a href="/cert/apply">민원 신청 내역</a>'))
            elif path == "/cert/apply":
                self._send(200, _page("민원 신청 내역", '<a href="/cert/home">홈</a>'))
            else:
                self._send(404, _page("없음", ""))
        else:
            self._send(404, _page("없음", ""))

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        form = parse_qs(self.rfile.read(length).decode())
        state = self.server.state
        if self.path == "/idpw/login":
            uid = form.get("uid", [""])[0]
            upw = form.get("upw", [""])[0]
            if uid == state.username and upw == state.password:
                self._send(302, location="/idpw/home", cookie=f"idpw_sid={state.issue()}")
            else:
                self._send(200, LOGIN_FORM.replace(b"</h1>", b"</h1><p>login failed</p>"))
        elif self.path == "/_test/approve":
            with state.lock:
                state.approved = True
            self._send(200, b"approved", content_type="text/plain")
        elif self.path == "/_test/expire":
            with state.lock:
                state.sessions.clear()
                state.approved = False
            self._send(200, b"expired", content_type="text/plain")
        else:
            self._send(404)

    def log_message(self, format: str, *args: object) -> None:
        pass


class SiteServer(ThreadingHTTPServer):
    def __init__(self, port: int, username: str, password: str) -> None:
        super().__init__(("127.0.0.1", port), Handler)
        self.state = SiteState(username, password)


def start_site(
    port: int = 0, username: str = FIXTURE_USERNAME, password: str = FIXTURE_PASSWORD
) -> SiteServer:
    server = SiteServer(port, username, password)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--username", default=FIXTURE_USERNAME)
    parser.add_argument("--password", default=FIXTURE_PASSWORD)
    args = parser.parse_args()
    SiteServer(args.port, args.username, args.password).serve_forever()
