"""에이전트 서버 실행: python -m legacy2next [--port 8000]."""

from __future__ import annotations

import argparse
import logging

import uvicorn
from dotenv import load_dotenv

from .api import create_app
from .config import REPO_ROOT, register_env_secrets
from .masking import secrets, setup_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Legacy2Next 에이전트 서버")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    # .env를 환경 변수로 올리고, 계정·키 값은 로그에 나오기 전에 마스킹 목록에 등록한다
    load_dotenv(REPO_ROOT / ".env")
    count = register_env_secrets(secrets)
    setup_logging()
    logging.getLogger("legacy2next").info("마스킹 대상 비밀값 %d개 등록", count)
    uvicorn.run(create_app(), host=args.host, port=args.port, log_config=None)


if __name__ == "__main__":
    main()
