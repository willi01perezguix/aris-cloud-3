from __future__ import annotations

from decimal import Decimal

from aris3_client_sdk.pos_cash_validation import (
    validate_cash_out_payload,
    validate_close_session_payload,
    validate_open_session_payload,
)


def test_open_session_validation_requires_fields() -> None:
    result = validate_open_session_payload(
        store_id="",
        opening_amount=Decimal("0.00"),
        business_date=None,
        timezone="",
    )
    reasons = {issue.field for issue in result.issues}
    assert "store_id" in reasons
    assert "opening_amount" in reasons
    assert "business_date" in reasons
    assert "timezone" in reasons


def test_cash_out_negative_balance_blocked() -> None:
    result = validate_cash_out_payload(
        Decimal("10.00"),
        reason=None,
        expected_balance=Decimal("5.00"),
    )
    assert result.ok is False
    assert any(issue.reason.startswith("would result") for issue in result.issues)


def test_close_session_requires_counted_cash() -> None:
    result = validate_close_session_payload(counted_cash=None, reason=None)
    assert result.ok is False
    assert any(issue.field == "counted_cash" for issue in result.issues)
