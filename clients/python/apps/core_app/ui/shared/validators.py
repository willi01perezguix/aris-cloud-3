from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

_EPC_HEX_24 = re.compile(r"^[0-9A-Fa-f]{24}$")


@dataclass
class ValidationResult:
    ok: bool
    field_errors: dict[str, str] = field(default_factory=dict)
    summary: list[str] = field(default_factory=list)


def _result(errors: dict[str, str]) -> ValidationResult:
    return ValidationResult(ok=not errors, field_errors=errors, summary=list(errors.values()))


def validate_import_epc_lines(lines: list[dict[str, Any]]) -> ValidationResult:
    errors: dict[str, str] = {}
    for idx, line in enumerate(lines):
        epc = str(line.get("epc") or "")
        qty = int(line.get("qty", 0) or 0)
        if not _EPC_HEX_24.match(epc):
            errors[f"lines[{idx}].epc"] = "EPC must be 24 HEX characters."
        if qty != 1:
            errors[f"lines[{idx}].qty"] = "EPC import quantity must be exactly 1."
    return _result(errors)


def validate_import_sku_lines(lines: list[dict[str, Any]]) -> ValidationResult:
    errors: dict[str, str] = {}
    for idx, line in enumerate(lines):
        qty = int(line.get("qty", 0) or 0)
        if qty <= 0:
            errors[f"lines[{idx}].qty"] = "SKU import quantity must be positive."
        if not line.get("sku"):
            errors[f"lines[{idx}].sku"] = "SKU is required."
    return _result(errors)


def validate_payments(payments: list[dict[str, Any]], total_due: Decimal) -> ValidationResult:
    errors: dict[str, str] = {}
    paid_total = Decimal("0")
    for idx, payment in enumerate(payments):
        method = str(payment.get("method") or "").upper()
        amount = Decimal(str(payment.get("amount", "0") or "0"))
        paid_total += amount
        if method == "CARD" and not payment.get("authorization_code"):
            errors[f"payments[{idx}].authorization_code"] = "CARD payment requires authorization_code."
        if method == "TRANSFER":
            if not payment.get("bank_name"):
                errors[f"payments[{idx}].bank_name"] = "TRANSFER payment requires bank_name."
            if not payment.get("voucher_number"):
                errors[f"payments[{idx}].voucher_number"] = "TRANSFER payment requires voucher_number."
    if paid_total < total_due:
        errors["totals.missing_amount"] = f"Missing amount: {(total_due - paid_total):.2f}"
    return _result(errors)
