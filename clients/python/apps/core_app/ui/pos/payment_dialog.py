from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from aris3_client_sdk import validate_checkout_payload


@dataclass
class PaymentDialog:
    total_due: Decimal
    payments: list[dict[str, Any]] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    def validate(self) -> bool:
        result = validate_checkout_payload(total_due=self.total_due, payments=self.payments)
        self.issues = [f"{issue.field}: {issue.reason}" for issue in result.issues]
        return result.ok

    def render(self) -> dict[str, Any]:
        result = validate_checkout_payload(total_due=self.total_due, payments=self.payments)
        return {
            "payments": self.payments,
            "issues": self.issues,
            "total_due": result.totals.total_due,
            "paid_total": result.totals.paid_total,
            "missing_amount": result.totals.missing_amount,
            "change_amount": result.totals.change_due,
            "cash_total": result.totals.cash_total,
        }
