from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_BASE_URL = "https://aris-cloud-3-api-pecul.ondigitalocean.app/"


@dataclass(frozen=True)
class AppConfig:
    base_url: str
    timeout_seconds: float
    verify_ssl: bool
    retry_max_attempts: int
    retry_backoff_ms: int

    @classmethod
    def from_env(cls, env_file: str = ".env") -> "AppConfig":
        _load_dotenv(env_file)
        config = cls(
            base_url=os.getenv("ARIS3_BASE_URL", DEFAULT_BASE_URL).strip(),
            timeout_seconds=float(os.getenv("ARIS3_TIMEOUT_SECONDS", "30")),
            verify_ssl=os.getenv("ARIS3_VERIFY_SSL", "true").lower() == "true",
            retry_max_attempts=int(os.getenv("ARIS3_RETRY_MAX_ATTEMPTS", "3")),
            retry_backoff_ms=int(os.getenv("ARIS3_RETRY_BACKOFF_MS", "150")),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if not self.base_url:
            raise ValueError("ARIS3_BASE_URL no puede estar vacío")
        if self.timeout_seconds <= 0:
            raise ValueError("ARIS3_TIMEOUT_SECONDS debe ser mayor a 0")
        if self.retry_max_attempts < 1:
            raise ValueError("ARIS3_RETRY_MAX_ATTEMPTS debe ser >= 1")
        if self.retry_backoff_ms < 0:
            raise ValueError("ARIS3_RETRY_BACKOFF_MS debe ser >= 0")


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
