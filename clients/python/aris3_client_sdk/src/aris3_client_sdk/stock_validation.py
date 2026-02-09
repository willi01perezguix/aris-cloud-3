from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, TypeVar

from pydantic import ValidationError as PydanticValidationError

from .models_stock import StockImportEpcLine, StockImportSkuLine, StockMigrateRequest

_HEX_24_RE = re.compile(r"^[0-9A-F]{24}$")
T = TypeVar("T")


@dataclass(frozen=True)
class ValidationIssue:
    row_index: int | None
    field: str
    reason: str


class ClientValidationError(ValueError):
    def __init__(self, issues: list[ValidationIssue]) -> None:
        self.issues = issues
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        if not self.issues:
            return "Validation failed"
        issue = self.issues[0]
        location = f"row {issue.row_index}" if issue.row_index is not None else "payload"
        return f"{location} {issue.field}: {issue.reason}"


def normalize_epc(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    return trimmed.upper()


def validate_epc_24_hex(value: str) -> None:
    if not _HEX_24_RE.match(value):
        raise ValueError("epc must be 24 hex characters (0-9, A-F)")


def validate_import_epc_line(line: StockImportEpcLine | Mapping[str, Any], row_index: int) -> StockImportEpcLine:
    data = _coerce_line(line, StockImportEpcLine, row_index)
    epc = normalize_epc(data.epc)
    if epc is None:
        _raise_issue(row_index, "epc", "epc is required for EPC imports")
    try:
        validate_epc_24_hex(epc)
    except ValueError as exc:
        _raise_issue(row_index, "epc", str(exc))
    if data.qty != 1:
        _raise_issue(row_index, "qty", "qty must be exactly 1 for EPC imports")
    if data.status != "RFID":
        _raise_issue(row_index, "status", "status must be RFID for EPC imports")
    return data.model_copy(update={"epc": epc})


def validate_import_sku_line(line: StockImportSkuLine | Mapping[str, Any], row_index: int) -> StockImportSkuLine:
    data = _coerce_line(line, StockImportSkuLine, row_index)
    epc = normalize_epc(data.epc)
    if epc:
        _raise_issue(row_index, "epc", "epc must be empty for SKU imports")
    if data.qty < 1:
        _raise_issue(row_index, "qty", "qty must be at least 1 for SKU imports")
    if data.status != "PENDING":
        _raise_issue(row_index, "status", "status must be PENDING for SKU imports")
    return data.model_copy(update={"epc": None})


def validate_migration_line(line: StockMigrateRequest | Mapping[str, Any], row_index: int = 0) -> StockMigrateRequest:
    payload = _coerce_line(line, StockMigrateRequest, row_index)
    epc = normalize_epc(payload.epc)
    if epc is None:
        _raise_issue(row_index, "epc", "epc is required for migration")
    try:
        validate_epc_24_hex(epc)
    except ValueError as exc:
        _raise_issue(row_index, "epc", str(exc))
    if payload.data.status != "PENDING":
        _raise_issue(row_index, "status", "status must be PENDING for migration")
    return payload.model_copy(update={"epc": epc})


def _coerce_line(line: T | Mapping[str, Any], model_type: type[T], row_index: int | None) -> T:
    if isinstance(line, model_type):
        return line
    try:
        return model_type.model_validate(line)
    except PydanticValidationError as exc:
        issue = exc.errors()[0] if exc.errors() else {"loc": ("line",), "msg": "Invalid line"}
        field = ".".join(str(part) for part in issue.get("loc", ("line",)))
        _raise_issue(row_index, field, issue.get("msg", "Invalid line"))
        raise


def _raise_issue(row_index: int | None, field: str, reason: str) -> None:
    raise ClientValidationError([ValidationIssue(row_index=row_index, field=field, reason=reason)])
