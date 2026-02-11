from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol


class FeatureFlagProvider(Protocol):
    def is_enabled(self, key: str) -> bool: ...


@dataclass
class DictFlagProvider:
    values: dict[str, bool]

    def is_enabled(self, key: str) -> bool:
        return bool(self.values.get(key, False))


@dataclass
class EnvFlagProvider:
    prefix: str = "ARIS3_FLAG_"

    def is_enabled(self, key: str) -> bool:
        env_key = f"{self.prefix}{key.upper()}"
        value = os.getenv(env_key, "0").strip().lower()
        return value in {"1", "true", "yes", "on"}
