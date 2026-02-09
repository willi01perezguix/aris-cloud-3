from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class CashValidationIssue:
    field: str
    reason: str


@dataclass(frozen=True)
class CashValidationResult:
    ok: bool
    issues: list[CashValidationIssue]


def _require_positive_amount(value: Decimal | None, field: str, issues: list[CashValidationIssue]) -> None:
    if value is None:
        issues.append(CashValidationIssue(field=field, reason="is required"))
        return
    if value <= 0:
        issues.append(CashValidationIssue(field=field, reason="must be greater than 0"))


def _require_non_empty(value: str | None, field: str, issues: list[CashValidationIssue]) -> None:
    if value is None or not value.strip():
        issues.append(CashValidationIssue(field=field, reason="is required"))


def validate_open_session_payload(
    *,
    store_id: str | None,
    opening_amount: Decimal | None,
    business_date: date | str | None,
    timezone: str | None,
) -> CashValidationResult:
    issues: list[CashValidationIssue] = []
    _require_non_empty(store_id, "store_id", issues)
    _require_positive_amount(opening_amount, "opening_amount", issues)
    if business_date is None or (isinstance(business_date, str) and not business_date.strip()):
        issues.append(CashValidationIssue(field="business_date", reason="is required"))
    _require_non_empty(timezone, "timezone", issues)
    return CashValidationResult(ok=not issues, issues=issues)


def validate_cash_in_payload(
    amount: Decimal | None,
    reason: str | None,
    *,
    require_reason: bool = False,
) -> CashValidationResult:
    issues: list[CashValidationIssue] = []
    _require_positive_amount(amount, "amount", issues)
    if require_reason:
        _require_non_empty(reason, "reason", issues)
    return CashValidationResult(ok=not issues, issues=issues)


def validate_cash_out_payload(
    amount: Decimal | None,
    reason: str | None,
    *,
    expected_balance: Decimal | None = None,
    expected_non_negative: bool = True,
    require_reason: bool = False,
) -> CashValidationResult:
    issues: list[CashValidationIssue] = []
    _require_positive_amount(amount, "amount", issues)
    if expected_non_negative and expected_balance is not None and amount is not None:
        if expected_balance - amount < 0:
            issues.append(CashValidationIssue(field="amount", reason="would result in negative drawer balance"))
    if require_reason:
        _require_non_empty(reason, "reason", issues)
    return CashValidationResult(ok=not issues, issues=issues)


def validate_close_session_payload(
    counted_cash: Decimal | None,
    reason: str | None,
    *,
    require_reason: bool = False,
) -> CashValidationResult:
    issues: list[CashValidationIssue] = []
    if counted_cash is None:
        issues.append(CashValidationIssue(field="counted_cash", reason="is required"))
    elif counted_cash < 0:
        issues.append(CashValidationIssue(field="counted_cash", reason="must be >= 0"))
    if require_reason:
        _require_non_empty(reason, "reason", issues)
    return CashValidationResult(ok=not issues, issues=issues)


def validate_day_close_payload(
    *,
    store_id: str | None,
    business_date: date | str | None,
    timezone: str | None,
    counted_cash: Decimal | None = None,
    require_reason: bool = False,
    reason: str | None = None,
) -> CashValidationResult:
    issues: list[CashValidationIssue] = []
    _require_non_empty(store_id, "store_id", issues)
    if business_date is None or (isinstance(business_date, str) and not business_date.strip()):
        issues.append(CashValidationIssue(field="business_date", reason="is required"))
    _require_non_empty(timezone, "timezone", issues)
    if counted_cash is not None and counted_cash < 0:
        issues.append(CashValidationIssue(field="counted_cash", reason="must be >= 0"))
    if require_reason:
        _require_non_empty(reason, "reason", issues)
    return CashValidationResult(ok=not issues, issues=issues)
