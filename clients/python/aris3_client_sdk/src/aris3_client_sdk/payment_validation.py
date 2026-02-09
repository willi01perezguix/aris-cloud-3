from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping, Sequence

from .models_pos_sales import PosPaymentCreate


@dataclass(frozen=True)
class PaymentValidationIssue:
    field: str
    reason: str


@dataclass(frozen=True)
class PaymentTotals:
    total_due: Decimal
    paid_total: Decimal
    missing_amount: Decimal
    change_due: Decimal
    cash_total: Decimal


@dataclass(frozen=True)
class PaymentValidationResult:
    ok: bool
    totals: PaymentTotals
    issues: list[PaymentValidationIssue]
    payments: list[PosPaymentCreate]


def compute_payment_totals(total_due: Decimal, payments: Sequence[PosPaymentCreate]) -> PaymentTotals:
    paid_total = sum((Decimal(str(payment.amount)) for payment in payments), Decimal("0.00"))
    cash_total = sum(
        (Decimal(str(payment.amount)) for payment in payments if payment.method == "CASH"),
        Decimal("0.00"),
    )
    missing_amount = max(total_due - paid_total, Decimal("0.00"))
    change_due = max(paid_total - total_due, Decimal("0.00"))
    return PaymentTotals(
        total_due=total_due,
        paid_total=paid_total,
        missing_amount=missing_amount,
        change_due=change_due,
        cash_total=cash_total,
    )


def validate_checkout_payload(
    *,
    total_due: Decimal | float | str,
    payments: Sequence[PosPaymentCreate | Mapping[str, Any]],
) -> PaymentValidationResult:
    normalized: list[PosPaymentCreate] = []
    issues: list[PaymentValidationIssue] = []
    for idx, payment in enumerate(payments):
        payload = payment if isinstance(payment, PosPaymentCreate) else PosPaymentCreate.model_validate(payment)
        method = (payload.method or "").upper()
        amount = Decimal(str(payload.amount))
        if amount <= 0:
            issues.append(
                PaymentValidationIssue(field=f"payments[{idx}].amount", reason="amount must be greater than 0")
            )
        if method == "CARD" and not payload.authorization_code:
            issues.append(
                PaymentValidationIssue(
                    field=f"payments[{idx}].authorization_code",
                    reason="authorization_code is required for CARD",
                )
            )
        if method == "TRANSFER" and (not payload.bank_name or not payload.voucher_number):
            issues.append(
                PaymentValidationIssue(
                    field=f"payments[{idx}].bank_name",
                    reason="bank_name and voucher_number are required for TRANSFER",
                )
            )
        normalized.append(payload.model_copy(update={"method": method}))

    totals = compute_payment_totals(Decimal(str(total_due)), normalized)
    if totals.missing_amount > 0:
        issues.append(
            PaymentValidationIssue(
                field="payments",
                reason="payments do not cover total due",
            )
        )
    if totals.change_due > totals.cash_total:
        issues.append(
            PaymentValidationIssue(
                field="payments",
                reason="change can only be given against CASH payments",
            )
        )

    return PaymentValidationResult(
        ok=not issues,
        totals=totals,
        issues=issues,
        payments=normalized,
    )
