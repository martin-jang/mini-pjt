"""설정 로더: config/settings.yaml(사이트·한도) + .env(비밀값)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .masking import SecretRegistry

AGENT_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = AGENT_DIR.parent
DEFAULT_CONFIG_PATH = AGENT_DIR / "config" / "settings.yaml"


def origin_of(url: str) -> str:
    """URL의 origin(scheme://host[:port])을 돌려준다. 기본 포트는 생략한다."""
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError(f"http(s) URL이 아닙니다: {url!r}")
    default_port = 443 if parts.scheme == "https" else 80
    port = f":{parts.port}" if parts.port and parts.port != default_port else ""
    return f"{parts.scheme}://{parts.hostname.lower()}{port}"


class Limits(BaseModel):
    """한 번 실행당 한도 (G8)."""

    llm_calls_per_run: int = Field(default=200, gt=0)
    verifier_retries: int = Field(default=3, ge=0)
    # Router(질의 분류) LLM 호출 수 상한. 실행 단위가 아니라 서버 프로세스 단위로 센다
    router_calls: int = Field(default=1000, gt=0)


class SiteConfig(BaseModel):
    """사이트별 설정. 사용자가 직접 적은 추가 origin만 허용한다 (G2)."""

    extra_origins: list[str] = Field(default_factory=list)
    # 시작 화면이 로그인 화면이 아닌 사이트의 로그인 화면 주소 (허용 origin 안이어야 한다)
    login_url: str | None = None
    # isolated: 에이전트가 띄우는 브라우저, extension: 사용자가 이미 로그인한 Chrome에 붙음
    # (보안 프로그램 때문에 자동화 브라우저로 인증이 안 되는 사이트, Playwright 확장 설치 필요)
    browser: Literal["isolated", "extension"] = "isolated"

    @field_validator("extra_origins")
    @classmethod
    def _normalize(cls, values: list[str]) -> list[str]:
        return [origin_of(v) for v in values]


class ExplorerConfig(BaseModel):
    """화면 수집 설정."""

    # mcp: Playwright MCP로 실제 브라우저 수집, stub: 예시 데이터 (브라우저 없이 흐름만 확인)
    mode: Literal["mcp", "stub"] = "mcp"
    headless: bool = True
    # Map(사이트맵) 상한: 수집 화면 수, 시작 화면에서 링크를 따라간 깊이, 같은 형태 URL 수
    max_screens: int = Field(default=40, ge=1)
    max_depth: int = Field(default=3, ge=0)
    max_per_pattern: int = Field(default=5, ge=1)
    # Walk(흐름 걷기): 완주 목표 수, 시도할 후보 수, 흐름 하나의 단계 상한
    walk_enabled: bool = True
    walk_target: int = Field(default=3, ge=1)
    walk_max_candidates: int = Field(default=6, ge=1)
    walk_max_steps: int = Field(default=8, ge=1)
    # 사용자 인증용 브라우저를 화면에 띄우지 않음 (테스트용. 실제로는 사용자가 창에서 인증한다)
    auth_headless: bool = False
    # 한 실행에서 로그인·인증을 다시 시도하는 횟수 상한 (세션 만료 재요청 포함)
    login_attempts: int = Field(default=3, ge=1)


class AgentConfig(BaseModel):
    """settings.yaml 내용."""

    limits: Limits = Field(default_factory=Limits)
    explorer: ExplorerConfig = Field(default_factory=ExplorerConfig)
    # 사이트별 생성 결과물 루트 (저장소 루트 기준). 에이전트는 이 아래 <별칭>/ 밖에 쓰지 않는다 (G9)
    output_root: Path = Path("next-pjt")
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    log_dir: Path = Path("logs")
    # LangGraph 체크포인트 SQLite 파일 (저장소 루트 기준, git 제외)
    checkpoint_path: Path = Path("checkpoints.sqlite")
    # 스텁 노드의 단계 간 지연(ms). 콘솔에서 진행이 흐르는 모습을 보기 위함
    stub_step_ms: int = Field(default=500, ge=0)
    # 로그인 세션(storageState) 저장 위치. next-pjt 밖의 git 제외 경로 (G10)
    session_dir: Path = Path("sessions")
    sites: dict[str, SiteConfig] = Field(default_factory=dict)

    def resolved_log_dir(self) -> Path:
        """log_dir가 상대 경로면 저장소 루트 기준으로 푼다."""
        return self.log_dir if self.log_dir.is_absolute() else REPO_ROOT / self.log_dir

    def site_dir(self, alias: str) -> Path:
        """사이트 결과물 폴더 next-pjt/<별칭>/."""
        root = self.output_root if self.output_root.is_absolute() else REPO_ROOT / self.output_root
        return root / alias

    def session_path(self, alias: str) -> Path:
        """사이트 로그인 세션 파일 sessions/<별칭>.json (생성 결과물과 분리, G10)."""
        root = self.session_dir if self.session_dir.is_absolute() else REPO_ROOT / self.session_dir
        return root / f"{alias}.json"

    def site(self, alias: str) -> SiteConfig:
        return self.sites.get(alias, SiteConfig())

    def resolved_checkpoint_path(self) -> Path:
        """checkpoint_path가 상대 경로면 저장소 루트 기준으로 푼다."""
        p = self.checkpoint_path
        return p if p.is_absolute() else REPO_ROOT / p

    def allowed_origins(self, alias: str, request_url: str) -> list[str]:
        """허용 origin = 요청 URL origin + 설정 파일의 추가 origin."""
        site = self.sites.get(alias, SiteConfig())
        origins = [origin_of(request_url), *site.extra_origins]
        return list(dict.fromkeys(origins))


class Secrets(BaseSettings):
    """.env에서 읽는 값. 계정은 사이트별 환경 변수로 따로 읽는다."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    aws_region: str = "ap-northeast-2"
    bedrock_model_id: str = "global.anthropic.claude-sonnet-4-6"
    # 거절(refusal) 시 다시 시도할 대체 모델. 비우면 대체하지 않는다
    bedrock_fallback_model_id: str = ""
    bedrock_embed_model_id: str = "amazon.titan-embed-text-v2:0"


class SiteCredentials(BaseModel):
    username: SecretStr
    password: SecretStr


def credential_env_prefix(alias: str) -> str:
    """별칭 hr-portal → SITE_HR_PORTAL."""
    return "SITE_" + alias.upper().replace("-", "_")


def load_site_credentials(
    alias: str, environ: dict[str, str] | None = None
) -> SiteCredentials | None:
    """사이트 계정을 환경 변수에서 읽는다. 둘 다 있어야 돌려준다."""
    env = os.environ if environ is None else environ
    prefix = credential_env_prefix(alias)
    username = env.get(f"{prefix}_USERNAME")
    password = env.get(f"{prefix}_PASSWORD")
    if not username or not password:
        return None
    return SiteCredentials(username=SecretStr(username), password=SecretStr(password))


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> AgentConfig:
    """settings.yaml을 읽어 검증한다. 파일이 없으면 기본값."""
    if not path.exists():
        return AgentConfig()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw["sites"] = raw.get("sites") or {}
    return AgentConfig.model_validate(raw)


SECRET_ENV_SUFFIXES = ("_USERNAME", "_PASSWORD", "_SECRET_ACCESS_KEY", "_SESSION_TOKEN")


def register_env_secrets(registry: SecretRegistry, environ: dict[str, str] | None = None) -> int:
    """계정·키 환경 변수 값을 마스킹 목록에 올린다 (G3). 등록한 개수를 돌려준다."""
    env = os.environ if environ is None else environ
    values = [v for k, v in env.items() if k.upper().endswith(SECRET_ENV_SUFFIXES) and v]
    registry.register(*values)
    return len(values)
