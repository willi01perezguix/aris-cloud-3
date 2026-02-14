from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BASE_URL = "https://aris-cloud-3-api-pecul.ondigitalocean.app/"


@dataclass(frozen=True)
class SDKConfig:
    base_url: str
    timeout_seconds: float
    verify_ssl: bool
    retry_max_attempts: int
    retry_backoff_ms: int

    @classmethod
    def from_env(cls, env_file: str = ".env") -> "SDKConfig":
        _load_dotenv(env_file)
        base_url = _normalize_base_url(os.getenv("ARIS3_BASE_URL", DEFAULT_BASE_URL))
        timeout_seconds = float(os.getenv("ARIS3_TIMEOUT_SECONDS", "30"))
        verify_ssl = parse_bool(os.getenv("ARIS3_VERIFY_SSL", "true"), default=True)
        retry_max_attempts = max(1, int(os.getenv("ARIS3_RETRY_MAX_ATTEMPTS", "3")))
        retry_backoff_ms = max(0, int(os.getenv("ARIS3_RETRY_BACKOFF_MS", "250")))
        return cls(
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            verify_ssl=verify_ssl,
            retry_max_attempts=retry_max_attempts,
            retry_backoff_ms=retry_backoff_ms,
        )


def _normalize_base_url(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        return DEFAULT_BASE_URL
    return normalized if normalized.endswith("/") else f"{normalized}/"


def parse_bool(value: str | bool | None, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default

    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "f", "no", "n", "off"}:
        return False
    return default


def _load_dotenv(path: str) -> None:
    dotenv_path = Path(path)
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())
