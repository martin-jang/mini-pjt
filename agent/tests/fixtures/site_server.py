"""G2 검증용 시험 사이트.

내부 링크, 다른 origin 링크, 다른 origin으로 가는 리다이렉트, 로그아웃 링크가 있다.

pytest에서는 start_site()로 스레드에서 띄우고, E2E에서는 스크립트로 띄운다:
    python tests/fixtures/site_server.py --port 8766
다른 origin은 같은 포트의 localhost(127.0.0.1과 origin이 다름)를 쓴다.
실제 외부 요청은 나가지 않는다.
"""

from __future__ import annotations

import argparse
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _page(title: str, body: str) -> bytes:
    return (
        f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>{title}</title></head>'
        f"<body><h1>{title}</h1>{body}</body></html>"
    ).encode()


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: bytes = b"", location: str | None = None) -> None:
        self.send_response(status)
        if location:
            self.send_header("Location", location)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 (http.server 규칙)
        port = self.server.server_address[1]
        external = f"http://localhost:{port}"
        if self.path in ("/", "/index.html"):
            self._send(
                200,
                _page(
                    "시험 사이트 홈",
                    (
                        '<a href="/page2.html">공지 목록</a> '
                        f'<a href="{external}/external.html">외부 사이트</a> '
                        '<a href="/go-out">외부로 가는 리다이렉트</a> '
                        '<a href="/logout">로그아웃</a>'
                    ),
                ),
            )
        elif self.path == "/page2.html":
            self._send(200, _page("공지 목록", '<a href="/">홈</a>'))
        elif self.path == "/go-out":
            self._send(302, location=f"{external}/external.html")
        elif self.path == "/external.html":
            self._send(200, _page("외부 페이지", "여기에 오면 안 된다"))
        else:
            self._send(404, _page("없음", ""))

    def log_message(self, format: str, *args: object) -> None:
        pass


def start_site(port: int = 0) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
