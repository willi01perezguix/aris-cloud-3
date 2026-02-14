from __future__ import annotations

import time
from typing import Any, Callable


def clean_filters(filters: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in filters.items() if value not in (None, "")}


def prompt_optional(label: str) -> str | None:
    value = input(f"{label} (opcional): ").strip()
    return value or None


def debounce_text(term: str, wait_ms: int = 350, sleeper: Callable[[float], None] | None = None) -> str:
    if wait_ms <= 0:
        return term
    (sleeper or time.sleep)(wait_ms / 1000)
    return term
