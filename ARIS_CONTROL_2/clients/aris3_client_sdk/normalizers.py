from __future__ import annotations

from typing import Any


def normalize_listing(payload: Any, *, page: int = 1, page_size: int = 20) -> dict[str, Any]:
    safe_page = max(1, int(page or 1))
    safe_page_size = max(1, int(page_size or 20))

    rows: list[Any] = []
    total: int | None = None
    has_next: bool | None = None
    has_prev: bool | None = None
    raw_meta: dict[str, Any] = {}

    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        if isinstance(payload.get("rows"), list):
            rows = payload["rows"]
        elif isinstance(payload.get("items"), list):
            rows = payload["items"]
        elif isinstance(payload.get("data"), list):
            rows = payload["data"]

        meta = payload.get("meta")
        if isinstance(meta, dict):
            raw_meta.update(meta)

        totals = payload.get("totals")
        if isinstance(totals, dict):
            raw_meta["totals"] = totals
            total = _to_int(totals.get("total") or totals.get("count"))

        total = total if total is not None else _to_int(payload.get("total"))
        total = total if total is not None else _to_int(raw_meta.get("total"))

        safe_page = _to_int(payload.get("page")) or _to_int(raw_meta.get("page")) or safe_page
        safe_page_size = (
            _to_int(payload.get("page_size"))
            or _to_int(payload.get("per_page"))
            or _to_int(raw_meta.get("page_size"))
            or _to_int(raw_meta.get("per_page"))
            or safe_page_size
        )

        has_next = _to_bool(payload.get("has_next"))
        if has_next is None:
            has_next = _to_bool(raw_meta.get("has_next"))
        has_prev = _to_bool(payload.get("has_prev"))
        if has_prev is None:
            has_prev = _to_bool(raw_meta.get("has_prev"))

    safe_page = max(1, int(safe_page))
    safe_page_size = max(1, int(safe_page_size))

    if total is None and isinstance(rows, list) and len(rows) < safe_page_size and safe_page == 1:
        total = len(rows)

    if has_prev is None:
        has_prev = safe_page > 1
    if has_next is None and total is not None:
        has_next = safe_page * safe_page_size < total

    return {
        "rows": rows if isinstance(rows, list) else [],
        "page": safe_page,
        "page_size": safe_page_size,
        "total": total,
        "has_next": has_next,
        "has_prev": has_prev,
        "raw_meta": raw_meta,
    }


def _to_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return None
