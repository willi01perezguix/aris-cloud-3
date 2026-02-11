from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass
class PaymentSummaryBar:
    total_due: Decimal
    paid_total: Decimal
    missing_amount: Decimal
    change_amount: Decimal
    cash_total: Decimal

    def render(self) -> dict[str, Any]:
        return {
            "total_due": self.total_due,
            "paid_total": self.paid_total,
            "missing_amount": self.missing_amount,
            "change_amount": self.change_amount,
            "cash_total": self.cash_total,
            "is_fully_paid": self.missing_amount == 0,
        }
