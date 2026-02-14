from clients.aris3_client_sdk.config import DEFAULT_BASE_URL, SDKConfig, parse_bool


def test_config_defaults(monkeypatch) -> None:
    monkeypatch.delenv("ARIS3_BASE_URL", raising=False)
    monkeypatch.delenv("ARIS3_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("ARIS3_VERIFY_SSL", raising=False)

    cfg = SDKConfig.from_env(env_file=".missing-env")

    assert cfg.base_url == DEFAULT_BASE_URL
    assert cfg.timeout_seconds == 30
    assert cfg.verify_ssl is True


def test_base_url_normalization_keeps_single_trailing_slash(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_BASE_URL", " https://example.test/api ")

    cfg = SDKConfig.from_env(env_file=".missing-env")

    assert cfg.base_url == "https://example.test/api/"


def test_parse_bool_common_variants() -> None:
    assert parse_bool("true") is True
    assert parse_bool("false") is False
    assert parse_bool("1") is True
    assert parse_bool("0") is False
    assert parse_bool("yes") is True
    assert parse_bool("no") is False
