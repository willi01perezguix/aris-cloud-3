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
    connect_timeout_seconds: float = 5.0
    read_timeout_seconds: float = 15.0
    retries: int = 3
    retry_backoff_seconds: float = 0.3
    max_connections: int = 20
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


def _read_float(name: str, default: str) -> float:
    raw = os.getenv(name, default)
    try:
        return float(raw)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"Invalid {name}: expected a number, got {raw!r}") from exc


def _read_int(name: str, default: str) -> int:
    raw = os.getenv(name, default)
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"Invalid {name}: expected an integer, got {raw!r}") from exc


def _validate(condition: bool, message: str) -> None:
    if not condition:
        raise ConfigError(message)


def load_config(env_file: str | None = None) -> ClientConfig:
    """Load config from environment with optional .env override."""
    load_dotenv(env_file)

    env_name = (os.getenv("ARIS3_ENV") or "dev").strip()
    env_key = env_name.upper()

    # Solo variables de entorno (sin fallback hardcodeado)
    api_base_url = (
        (os.getenv(f"ARIS3_API_BASE_URL_{env_key}") or "").strip()
        or (os.getenv("ARIS3_API_BASE_URL") or "").strip()
    )

    timeout_seconds = _read_float("ARIS3_TIMEOUT_SECONDS", "10")
    _validate(
        timeout_seconds > 0,
        f"Invalid ARIS3_TIMEOUT_SECONDS: expected > 0, got {timeout_seconds}",
    )

    connect_timeout_seconds = _read_float(
        "ARIS3_CONNECT_TIMEOUT_SECONDS", str(min(timeout_seconds, 5.0))
    )
    _validate(
        connect_timeout_seconds > 0,
        (
            "Invalid ARIS3_CONNECT_TIMEOUT_SECONDS: "
            f"expected > 0, got {connect_timeout_seconds}"
        ),
    )

    read_timeout_seconds = _read_float(
        "ARIS3_READ_TIMEOUT_SECONDS",
        str(max(timeout_seconds, connect_timeout_seconds)),
    )
    _validate(
        read_timeout_seconds > 0,
        f"Invalid ARIS3_READ_TIMEOUT_SECONDS: expected > 0, got {read_timeout_seconds}",
    )

    retries = _read_int("ARIS3_RETRIES", "3")
    _validate(retries >= 0, f"Invalid ARIS3_RETRIES: expected >= 0, got {retries}")

    retry_backoff_seconds = _read_float("ARIS3_RETRY_BACKOFF_SECONDS", "0.3")
    _validate(
        retry_backoff_seconds >= 0,
        (
            "Invalid ARIS3_RETRY_BACKOFF_SECONDS: "
            f"expected >= 0, got {retry_backoff_seconds}"
        ),
    )

    max_connections = _read_int("ARIS3_MAX_CONNECTIONS", "20")
    _validate(
        max_connections >= 1,
        f"Invalid ARIS3_MAX_CONNECTIONS: expected >= 1, got {max_connections}",
    )

    verify_ssl = _coerce_bool(os.getenv("ARIS3_VERIFY_SSL"), True)

    values = {"ARIS3_API_BASE_URL": api_base_url}
    _require(values, ["ARIS3_API_BASE_URL"])

    return ClientConfig(
        env_name=env_name,
        api_base_url=api_base_url.rstrip("/"),
        connect_timeout_seconds=connect_timeout_seconds,
        read_timeout_seconds=read_timeout_seconds,
        retries=retries,
        retry_backoff_seconds=retry_backoff_seconds,
        max_connections=max_connections,
        verify_ssl=verify_ssl,
    )
