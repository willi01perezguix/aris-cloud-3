from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


class CoreAppConfigError(ValueError):
    """Raised when required core app configuration is missing."""


@dataclass(frozen=True)
class CoreAppConfig:
    env_mode: str
    api_base_url: str
    connect_timeout_seconds: float
    read_timeout_seconds: float
    app_id: str | None = None
    device_id: str | None = None



def load_core_app_config(env_file: str | None = None) -> CoreAppConfig:
    load_dotenv(env_file)

    env_mode = os.getenv("ARIS3_ENV", "dev").strip().lower()
    env_key = env_mode.upper()
    api_base_url = os.getenv(f"ARIS3_API_BASE_URL_{env_key}") or os.getenv("ARIS3_API_BASE_URL")
    if not api_base_url:
        raise CoreAppConfigError(
            "Missing required configuration ARIS3_API_BASE_URL (or ARIS3_API_BASE_URL_<ENV>)."
        )

    connect_timeout = float(os.getenv("ARIS3_CONNECT_TIMEOUT_SECONDS", "5"))
    read_timeout = float(os.getenv("ARIS3_READ_TIMEOUT_SECONDS", "15"))

    return CoreAppConfig(
        env_mode=env_mode,
        api_base_url=api_base_url.rstrip("/"),
        connect_timeout_seconds=connect_timeout,
        read_timeout_seconds=read_timeout,
        app_id=os.getenv("ARIS3_APP_ID"),
        device_id=os.getenv("ARIS3_DEVICE_ID"),
    )
