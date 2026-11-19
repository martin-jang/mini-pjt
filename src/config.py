"""설정 로더.

config/settings.yaml을 읽어 한 번만 캐시합니다. 사이트 고유 값(허용 도메인, 시작 URL,
데모 계정 환경변수 이름)은 반드시 이 설정을 통해서만 가져옵니다. 에이전트 코드에
특정 사이트 값을 직접 쓰지 않기 위한 단일 진입점입니다.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# 저장소 루트 (src/의 상위 폴더)
ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = ROOT / "config" / "settings.yaml"

load_dotenv(ROOT / ".env")


@lru_cache(maxsize=1)
def settings() -> dict[str, Any]:
    """settings.yaml 전체를 dict로 반환합니다. 파일이 없으면 명확한 오류를 냅니다."""
    if not SETTINGS_PATH.exists():
        raise FileNotFoundError(f"설정 파일이 없습니다: {SETTINGS_PATH}")
    return yaml.safe_load(SETTINGS_PATH.read_text(encoding="utf-8"))


def path(key: str) -> Path:
    """settings.paths.<key>를 저장소 루트 기준 절대 경로로 돌려줍니다."""
    return ROOT / settings()["paths"][key]


def allowed_domains() -> list[str]:
    """크롤링 허용 도메인 목록 (가드레일 G1)."""
    return [d.lower() for d in settings()["target"]["allowed_domains"]]


def demo_credentials() -> tuple[str | None, str | None]:
    """데모 계정 (아이디, 비밀번호). 값은 .env에서 읽고, 없으면 None."""
    env = settings()["target"]["demo_account_env"]
    return os.getenv(env["username"]), os.getenv(env["password"])
