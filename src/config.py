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


def targets() -> list[dict[str, Any]]:
    """분석 대상 사이트 설정 목록. 첫 번째(target)가 기본 대상이고, extra_targets 가 추가 대상입니다.

    사이트별로 다른 값(허용 도메인, 시작 URL, 데모 계정 환경변수 이름, 결과물 이름, 1회 제출 폼)은
    모두 여기서만 가져옵니다. 새 레거시를 붙일 때는 코드가 아니라 settings.yaml 에 항목을 추가합니다.
    """
    s = settings()
    return [s["target"], *(s.get("extra_targets") or [])]


def _host_match(host: str, domains: list[str]) -> bool:
    host = (host or "").lower()
    return any(host == d.lower() or host.endswith("." + d.lower()) for d in domains)


def target_for(domain: str | None = None) -> dict[str, Any]:
    """도메인(호스트)에 해당하는 대상 설정. 없거나 모르는 도메인이면 기본 대상(target)."""
    if domain:
        for t in targets():
            if _host_match(domain, t.get("allowed_domains", [])):
                return t
    return settings()["target"]


def allowed_domains() -> list[str]:
    """크롤링 허용 도메인 목록 (가드레일 G1). 모든 대상 설정의 허용 도메인을 합친 것입니다."""
    seen: list[str] = []
    for t in targets():
        for d in t.get("allowed_domains", []):
            if d.lower() not in seen:
                seen.append(d.lower())
    return seen


def loopback_allowed(host: str, port: int | None) -> bool:
    """G1 예외: 로컬에 띄운 레거시 샘플(127.0.0.1)을 분석할 수 있는지.

    대상 설정에 allow_loopback_ports 가 명시되어 있고, 호스트가 그 대상의 허용 도메인이며,
    포트가 목록에 있을 때만 True 입니다. 그 밖의 사설망·메타데이터 주소는 여전히 막습니다.
    """
    for t in targets():
        ports = t.get("allow_loopback_ports") or []
        if ports and _host_match(host, t.get("allowed_domains", [])) and port in ports:
            return True
    return False


def demo_credentials(domain: str | None = None) -> tuple[str | None, str | None]:
    """대상 사이트의 데모 계정 (아이디, 비밀번호). 값은 .env에서 읽고, 없으면 None."""
    env = target_for(domain).get("demo_account_env") or {}
    return os.getenv(env.get("username", "")), os.getenv(env.get("password", ""))


def fixture_domains_for(domain: str | None) -> list[str]:
    """domain 을 복제해 만든 합성 픽스처 도메인 목록 (data/fixtures/<픽스처>/*.json 안에 원본 도메인 주소가 있으면 연결).

    픽스처는 원본 시스템 화면에 변이를 주입한 교육용 데이터라, 원본 시스템의 질의·통일 결정 자료로만 씁니다.
    사이트 이름을 코드에 두지 않기 위해 파일 내용으로 연결합니다.
    """
    if not domain:
        return []
    host = domain.split(":")[0]
    root = path("fixtures")
    if not root.is_dir():
        return []
    return sorted(d.name for d in root.iterdir() if d.is_dir() and d.name != host
                  and any(host in f.read_text(encoding="utf-8", errors="ignore") for f in d.glob("*.json")))
