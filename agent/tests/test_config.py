from pathlib import Path

import pytest

from legacy2next.config import (
    AgentConfig,
    credential_env_prefix,
    load_config,
    load_site_credentials,
    origin_of,
)


def test_origin_of_normalizes_scheme_host_and_default_port():
    assert origin_of("https://Legacy.Example.com:443/login?x=1") == "https://legacy.example.com"
    assert origin_of("http://localhost:8080/app") == "http://localhost:8080"


@pytest.mark.parametrize("url", ["ftp://example.com", "example.com", "javascript:alert(1)"])
def test_origin_of_rejects_non_http(url):
    with pytest.raises(ValueError):
        origin_of(url)


def test_allowed_origins_adds_only_configured_extra_origins():
    cfg = AgentConfig.model_validate(
        {"sites": {"hr-portal": {"extra_origins": ["https://sso.example.com/auth"]}}}
    )
    assert cfg.allowed_origins("hr-portal", "https://hr.example.com/main") == [
        "https://hr.example.com",
        "https://sso.example.com",
    ]
    # 설정 없는 사이트는 요청 origin만
    assert cfg.allowed_origins("other", "https://other.example.com") == [
        "https://other.example.com"
    ]


def test_load_config_reads_repo_settings_file():
    cfg = load_config()
    assert cfg.limits.llm_calls_per_run > 0
    assert cfg.limits.verifier_retries == 3


def test_load_config_missing_file_uses_defaults(tmp_path: Path):
    cfg = load_config(tmp_path / "none.yaml")
    assert cfg == AgentConfig()


def test_load_config_validates_limits(tmp_path: Path):
    path = tmp_path / "s.yaml"
    path.write_text("limits:\n  llm_calls_per_run: 0\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(path)


def test_site_credentials_from_env_by_alias():
    assert credential_env_prefix("hr-portal") == "SITE_HR_PORTAL"
    env = {"SITE_HR_PORTAL_USERNAME": "user01", "SITE_HR_PORTAL_PASSWORD": "pw-secret"}
    creds = load_site_credentials("hr-portal", env)
    assert creds is not None
    assert creds.password.get_secret_value() == "pw-secret"
    assert "pw-secret" not in repr(creds)
    assert load_site_credentials("hr-portal", {"SITE_HR_PORTAL_USERNAME": "u"}) is None


def test_register_env_secrets_picks_credentials_and_aws_keys():
    from legacy2next.config import register_env_secrets
    from legacy2next.masking import SecretRegistry

    reg = SecretRegistry()
    env = {
        "SITE_HR_PORTAL_USERNAME": "user01",
        "SITE_HR_PORTAL_PASSWORD": "pw-secret",
        "AWS_SECRET_ACCESS_KEY": "aws-secret-key",
        "AWS_REGION": "ap-northeast-2",
    }
    assert register_env_secrets(reg, env) == 3
    assert (
        reg.mask("user01 pw-secret aws-secret-key ap-northeast-2") == "*** *** *** ap-northeast-2"
    )
