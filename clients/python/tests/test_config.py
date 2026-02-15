from __future__ import annotations

import pytest

from aris3_client_sdk.config import ConfigError, load_config


def test_load_config_requires_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARIS3_API_BASE_URL", raising=False)
    monkeypatch.delenv("ARIS3_API_BASE_URL_DEV", raising=False)
    monkeypatch.delenv("ARIS3_ENV", raising=False)
    with pytest.raises(ConfigError):
        load_config()


def test_load_config_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARIS3_ENV", "staging")
    monkeypatch.setenv("ARIS3_API_BASE_URL_STAGING", "https://staging.example.com")
    cfg = load_config()
    assert cfg.api_base_url == "https://staging.example.com"
    assert cfg.env_name == "staging"


@pytest.mark.parametrize(
    ("key", "value", "snippet"),
    [
        ("ARIS3_TIMEOUT_SECONDS", "0", "ARIS3_TIMEOUT_SECONDS"),
        ("ARIS3_CONNECT_TIMEOUT_SECONDS", "0", "ARIS3_CONNECT_TIMEOUT_SECONDS"),
        ("ARIS3_READ_TIMEOUT_SECONDS", "0", "ARIS3_READ_TIMEOUT_SECONDS"),
        ("ARIS3_RETRIES", "-1", "ARIS3_RETRIES"),
        ("ARIS3_RETRY_BACKOFF_SECONDS", "-0.1", "ARIS3_RETRY_BACKOFF_SECONDS"),
        ("ARIS3_MAX_CONNECTIONS", "0", "ARIS3_MAX_CONNECTIONS"),
    ],
)
def test_load_config_rejects_invalid_ranges(
    monkeypatch: pytest.MonkeyPatch,
    key: str,
    value: str,
    snippet: str,
) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    monkeypatch.setenv(key, value)

    with pytest.raises(ConfigError, match=snippet):
        load_config()


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("ARIS3_TIMEOUT_SECONDS", "abc"),
        ("ARIS3_CONNECT_TIMEOUT_SECONDS", "abc"),
        ("ARIS3_READ_TIMEOUT_SECONDS", "abc"),
        ("ARIS3_RETRIES", "abc"),
        ("ARIS3_RETRY_BACKOFF_SECONDS", "abc"),
        ("ARIS3_MAX_CONNECTIONS", "abc"),
    ],
)
def test_load_config_rejects_invalid_types(
    monkeypatch: pytest.MonkeyPatch,
    key: str,
    value: str,
) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    monkeypatch.setenv(key, value)

    with pytest.raises(ConfigError, match=key):
        load_config()


def test_load_config_retry_jitter_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("ARIS3_RETRY_JITTER_ENABLED", "true")
    monkeypatch.setenv("ARIS3_RETRY_JITTER_MIN_SECONDS", "0.05")
    monkeypatch.setenv("ARIS3_RETRY_JITTER_MAX_SECONDS", "0.2")

    cfg = load_config()

    assert cfg.retry_jitter_enabled is True
    assert cfg.retry_jitter_min_seconds == 0.05
    assert cfg.retry_jitter_max_seconds == 0.2


def test_load_config_rejects_invalid_retry_jitter_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("ARIS3_RETRY_JITTER_MIN_SECONDS", "0.2")
    monkeypatch.setenv("ARIS3_RETRY_JITTER_MAX_SECONDS", "0.1")

    with pytest.raises(ConfigError, match="ARIS3_RETRY_JITTER_MAX_SECONDS"):
        load_config()
