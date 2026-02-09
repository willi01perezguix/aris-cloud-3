from __future__ import annotations

from decimal import Decimal

from aris3_client_sdk.models_pos_sales import PosPaymentCreate
from aris3_client_sdk.payment_validation import compute_payment_totals, validate_checkout_payload


def test_payment_totals_math() -> None:
    totals = compute_payment_totals(
        Decimal("10.00"),
        [
            PosPaymentCreate(method="CASH", amount=6.0),
            PosPaymentCreate(method="CARD", amount=6.0, authorization_code="AUTH"),
        ],
    )
    assert totals.paid_total == Decimal("12.00")
    assert totals.missing_amount == Decimal("0.00")
    assert totals.change_due == Decimal("2.00")


def test_card_requires_authorization_code() -> None:
    result = validate_checkout_payload(
        total_due=Decimal("5.00"),
        payments=[{"method": "CARD", "amount": 5.0}],
    )
    assert result.ok is False
    assert any("authorization_code" in issue.field for issue in result.issues)


def test_transfer_requires_bank_and_voucher() -> None:
    result = validate_checkout_payload(
        total_due=Decimal("5.00"),
        payments=[{"method": "TRANSFER", "amount": 5.0}],
    )
    assert result.ok is False
    assert any("bank_name" in issue.field for issue in result.issues)


def test_change_only_from_cash() -> None:
    result = validate_checkout_payload(
        total_due=Decimal("5.00"),
        payments=[{"method": "CARD", "amount": 7.0, "authorization_code": "AUTH"}],
    )
    assert result.ok is False
    assert any("change" in issue.reason.lower() for issue in result.issues)


def test_missing_amount_detected() -> None:
    result = validate_checkout_payload(
        total_due=Decimal("10.00"),
        payments=[{"method": "CASH", "amount": 5.0}],
    )
    assert result.ok is False
    assert any("cover" in issue.reason.lower() for issue in result.issues)
