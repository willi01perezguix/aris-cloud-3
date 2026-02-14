from __future__ import annotations

from typing import Any


def clean_filters(filters: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in filters.items() if value not in (None, "")}


def prompt_optional(label: str) -> str | None:
    value = input(f"{label} (opcional): ").strip()
    return value or None
