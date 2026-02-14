from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CacheEntry:
    value: dict[str, Any]
    expires_at: float


class ListingCache:
    """Small in-memory TTL cache for read-only listing payloads."""

    def __init__(self, ttl_seconds: float = 20.0, now: Callable[[], float] | None = None) -> None:
        self.ttl_seconds = max(1.0, ttl_seconds)
        self._now = now or time.monotonic
        self._entries: dict[str, CacheEntry] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        entry = self._entries.get(key)
        if not entry:
            return None
        if entry.expires_at <= self._now():
            self._entries.pop(key, None)
            return None
        return entry.value

    def set(self, key: str, value: dict[str, Any]) -> None:
        self._entries[key] = CacheEntry(value=value, expires_at=self._now() + self.ttl_seconds)

    def invalidate_prefix(self, prefix: str) -> None:
        stale_keys = [key for key in self._entries if key.startswith(prefix)]
        for key in stale_keys:
            self._entries.pop(key, None)

    def clear(self) -> None:
        self._entries.clear()
