from aris_control_2.app.config import AppConfig, DEFAULT_BASE_URL


def test_app_config_default_base_url_is_official(monkeypatch) -> None:
    monkeypatch.delenv("ARIS3_BASE_URL", raising=False)

    cfg = AppConfig.from_env(env_file=".missing-env")

    assert cfg.base_url == DEFAULT_BASE_URL
