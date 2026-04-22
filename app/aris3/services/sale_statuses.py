from __future__ import annotations

FINALIZED_SALE_STATUSES = frozenset({"PAID", "COMPLETED", "CLOSED", "FINALIZED"})


def is_finalized_sale_status(status: str | None) -> bool:
    return str(status or "").upper() in FINALIZED_SALE_STATUSES
