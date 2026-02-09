from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable

from dotenv import load_dotenv


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class ClientConfig:
    env_name: str
    api_base_url: str
    timeout_seconds: float = 10.0
    retries: int = 3
    verify_ssl: bool = True

    @property
    def normalized_env(self) -> str:
        return self.env_name.lower().strip()


def _require(values: dict[str, str | None], required: Iterable[str]) -> None:
    missing = [key for key in required if not values.get(key)]
    if missing:
        raise ConfigError(f"Missing required config values: {', '.join(missing)}")


def _coerce_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_config(env_file: str | None = None) -> ClientConfig:
    """Load config from environment with optional .env override."""
    load_dotenv(env_file)
    env_name = os.getenv("ARIS3_ENV", "dev")
    env_key = env_name.upper()
    api_base_url = os.getenv(f"ARIS3_API_BASE_URL_{env_key}") or os.getenv("ARIS3_API_BASE_URL")
    timeout_seconds = float(os.getenv("ARIS3_TIMEOUT_SECONDS", "10"))
    retries = int(os.getenv("ARIS3_RETRIES", "3"))
    verify_ssl = _coerce_bool(os.getenv("ARIS3_VERIFY_SSL"), True)

    values = {
        "ARIS3_API_BASE_URL": api_base_url,
    }
    _require(values, ["ARIS3_API_BASE_URL"])

    return ClientConfig(
        env_name=env_name,
        api_base_url=api_base_url.rstrip("/"),
        timeout_seconds=timeout_seconds,
        retries=retries,
        verify_ssl=verify_ssl,
    )
