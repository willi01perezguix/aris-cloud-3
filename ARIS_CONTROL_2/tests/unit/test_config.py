from clients.aris3_client_sdk.config import DEFAULT_BASE_URL, SDKConfig, parse_bool


def test_base_url_normalizes_trailing_slash(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_BASE_URL", "https://example.com/api")
    monkeypatch.delenv("ARIS3_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("ARIS3_VERIFY_SSL", raising=False)

    cfg = SDKConfig.from_env(env_file=".missing-env")

    assert cfg.base_url == "https://example.com/api/"


def test_base_url_default_is_official(monkeypatch) -> None:
    monkeypatch.delenv("ARIS3_BASE_URL", raising=False)
    cfg = SDKConfig.from_env(env_file=".missing-env")
    assert cfg.base_url == DEFAULT_BASE_URL


def test_parse_verify_ssl_variants() -> None:
    assert parse_bool("true") is True
    assert parse_bool("FALSE") is False
    assert parse_bool("1") is True
    assert parse_bool("0") is False
    assert parse_bool("invalid", default=True) is True
    assert parse_bool("invalid", default=False) is False
