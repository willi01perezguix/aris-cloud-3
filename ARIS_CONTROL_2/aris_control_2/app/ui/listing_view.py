from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

EMPTY_VALUE = "—"
SENSITIVE_KEYS = {"token", "refresh_token", "secret", "password", "access_token"}


@dataclass(frozen=True)
class ColumnDef:
    key: str
    label: str


@dataclass
class ListingViewState:
    visible_columns: list[str]
    sort_by: str | None = None
    sort_dir: str = "asc"


def default_view_state(columns: list[ColumnDef]) -> ListingViewState:
    return ListingViewState(visible_columns=[column.key for column in columns], sort_by=None, sort_dir="asc")


def hydrate_view_state(payload: dict[str, Any] | None, columns: list[ColumnDef]) -> ListingViewState:
    default = default_view_state(columns)
    allowed = {column.key for column in columns}
    if not isinstance(payload, dict):
        return default

    selected = payload.get("visible_columns")
    visible = [str(key) for key in selected if str(key) in allowed] if isinstance(selected, list) else default.visible_columns
    if not visible:
        visible = default.visible_columns

    sort_by = payload.get("sort_by")
    resolved_sort = str(sort_by) if sort_by in allowed else None
    sort_dir = "desc" if str(payload.get("sort_dir", "asc")).lower() == "desc" else "asc"
    return ListingViewState(visible_columns=visible, sort_by=resolved_sort, sort_dir=sort_dir)


def serialize_view_state(view: ListingViewState) -> dict[str, Any]:
    return {"visible_columns": list(view.visible_columns), "sort_by": view.sort_by, "sort_dir": view.sort_dir}


def sort_rows(rows: list[dict[str, Any]], view: ListingViewState) -> list[dict[str, Any]]:
    if not view.sort_by:
        return list(rows)

    def _sort_key(row: dict[str, Any]) -> tuple[int, str]:
        value = normalize_value(row.get(view.sort_by))
        return (1 if value == EMPTY_VALUE else 0, value.lower())

    return sorted(rows, key=_sort_key, reverse=view.sort_dir == "desc")


def normalize_value(value: Any) -> str:
    if value is None:
        return EMPTY_VALUE
    if isinstance(value, str):
        clean = value.strip()
        if not clean:
            return EMPTY_VALUE
        lower = clean.lower()
        if lower in {"active", "inactive", "suspended", "pending"}:
            return lower.upper()
        return clean
    if isinstance(value, bool):
        return "ACTIVE" if value else "INACTIVE"
    if isinstance(value, datetime):
        return value.astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    return str(value)


def sanitize_row(row: dict[str, Any], headers: list[str]) -> dict[str, str]:
    sanitized: dict[str, str] = {}
    for header in headers:
        if any(token in header.lower() for token in SENSITIVE_KEYS):
            sanitized[header] = EMPTY_VALUE
            continue
        sanitized[header] = normalize_value(row.get(header))
    return sanitized
