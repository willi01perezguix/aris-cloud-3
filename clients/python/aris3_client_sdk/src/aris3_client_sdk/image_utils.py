from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.parse import urlparse


def safe_image_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return None
    if not parsed.netloc:
        return None
    return value


def choose_best_image(asset: object, *, prefer_thumb: bool = True) -> str | None:
    thumb = safe_image_url(getattr(asset, "thumb_url", None))
    full = safe_image_url(getattr(asset, "url", None))
    if prefer_thumb:
        return thumb or full
    return full or thumb


def placeholder_image_ref() -> str:
    return "placeholder://aris-image"


@dataclass
class ImageMemoCache:
    ttl_seconds: int = 300

    def __post_init__(self) -> None:
        self._entries: dict[str, tuple[float, object]] = {}

    def get(self, key: str) -> object | None:
        entry = self._entries.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if expires_at < time.time():
            self._entries.pop(key, None)
            return None
        return value

    def set(self, key: str, value: object) -> None:
        self._entries[key] = (time.time() + max(1, self.ttl_seconds), value)
