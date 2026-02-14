import os

from aris_control_2.app.config import AppConfig


def test_config_defaults(monkeypatch) -> None:
    for key in [
        "ARIS3_BASE_URL",
        "ARIS3_TIMEOUT_SECONDS",
        "ARIS3_VERIFY_SSL",
        "ARIS3_RETRY_MAX_ATTEMPTS",
        "ARIS3_RETRY_BACKOFF_MS",
    ]:
        monkeypatch.delenv(key, raising=False)

    config = AppConfig.from_env(".missing-env")

    assert config.base_url == "http://localhost:8000"
    assert config.retry_max_attempts == 3


def test_config_validation(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_TIMEOUT_SECONDS", "0")
    try:
        AppConfig.from_env(".missing-env")
        raised = False
    except ValueError:
        raised = True

    assert raised
    os.environ.pop("ARIS3_TIMEOUT_SECONDS", None)
