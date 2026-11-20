"""에이전트 서버 실행: python -m legacy2next [--port 8000]."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

from .api import create_app
from .config import REPO_ROOT, load_config, register_env_secrets
from .masking import secrets, setup_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Legacy2Next 에이전트 서버")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    # 아래는 settings.yaml 값을 덮어쓴다 (E2E 테스트에서 격리된 저장 위치를 쓰기 위함)
    parser.add_argument("--log-dir", type=Path)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--stub-step-ms", type=int)
    parser.add_argument("--output-root", type=Path, help="next-pjt 대신 쓸 결과물 루트")
    parser.add_argument("--session-dir", type=Path, help="로그인 세션 저장 폴더 (git 제외 경로)")
    parser.add_argument(
        "--auth-headless", action="store_true", help="사용자 인증 브라우저 창을 띄우지 않음 (E2E용)"
    )
    parser.add_argument("--cors-origin", action="append", default=[])
    parser.add_argument(
        "--fake-llm", action="store_true", help="실제 Bedrock 대신 테스트용 가짜 LLM (E2E용)"
    )
    args = parser.parse_args()

    # .env를 환경 변수로 올리고, 계정·키 값은 로그에 나오기 전에 마스킹 목록에 등록한다
    load_dotenv(REPO_ROOT / ".env")
    count = register_env_secrets(secrets)
    setup_logging()
    logging.getLogger("legacy2next").info("마스킹 대상 비밀값 %d개 등록", count)

    config = load_config()
    overrides: dict[str, object] = {}
    if args.log_dir:
        overrides["log_dir"] = args.log_dir.resolve()
    if args.checkpoint:
        overrides["checkpoint_path"] = args.checkpoint.resolve()
    if args.output_root:
        overrides["output_root"] = args.output_root.resolve()
    if args.stub_step_ms is not None:
        overrides["stub_step_ms"] = args.stub_step_ms
    if args.session_dir:
        overrides["session_dir"] = args.session_dir.resolve()
    if args.auth_headless:
        overrides["explorer"] = config.explorer.model_copy(update={"auth_headless": True})
    if args.cors_origin:
        overrides["cors_origins"] = [*config.cors_origins, *args.cors_origin]
    config = config.model_copy(update=overrides)

    uvicorn.run(
        create_app(config, fake_llm=args.fake_llm), host=args.host, port=args.port, log_config=None
    )


if __name__ == "__main__":
    main()
