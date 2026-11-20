"""설정 로더: config/settings.yaml(사이트·한도) + .env(비밀값)."""

from __future__ import annotations

import os
from pathlib import Path
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

    @field_validator("extra_origins")
    @classmethod
    def _normalize(cls, values: list[str]) -> list[str]:
        return [origin_of(v) for v in values]


class AgentConfig(BaseModel):
    """settings.yaml 내용."""

    limits: Limits = Field(default_factory=Limits)
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    log_dir: Path = Path("logs")
    # LangGraph 체크포인트 SQLite 파일 (저장소 루트 기준, git 제외)
    checkpoint_path: Path = Path("checkpoints.sqlite")
    # 스텁 노드의 단계 간 지연(ms). 콘솔에서 진행이 흐르는 모습을 보기 위함
    stub_step_ms: int = Field(default=500, ge=0)
    sites: dict[str, SiteConfig] = Field(default_factory=dict)

    def resolved_log_dir(self) -> Path:
        """log_dir가 상대 경로면 저장소 루트 기준으로 푼다."""
        return self.log_dir if self.log_dir.is_absolute() else REPO_ROOT / self.log_dir

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
