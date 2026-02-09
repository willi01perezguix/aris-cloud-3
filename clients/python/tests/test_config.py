from __future__ import annotations

import os

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
