from __future__ import annotations

from typing import Any, Mapping, TypeVar

from pydantic import ValidationError as PydanticValidationError

from .models_transfers import (
    CancelRequest,
    DispatchRequest,
    ReceiveRequest,
    ReportShortagesRequest,
    ResolveShortagesRequest,
    TransferCreateRequest,
    TransferLineCreate,
    TransferReceiveLine,
    TransferShortageLine,
    TransferShortageResolution,
    TransferShortageResolutionLine,
    TransferUpdateRequest,
)
from .stock_validation import ClientValidationError, ValidationIssue

T = TypeVar("T")


def validate_create_transfer_payload(payload: TransferCreateRequest | Mapping[str, Any]) -> TransferCreateRequest:
    data = _coerce_model(payload, TransferCreateRequest, None)
    if data.origin_store_id == data.destination_store_id:
        _raise_issue(None, "origin_store_id", "origin_store_id and destination_store_id must differ")
    if not data.lines:
        _raise_issue(None, "lines", "lines must not be empty")
    validated = [validate_transfer_line(line, idx) for idx, line in enumerate(data.lines)]
    return data.model_copy(update={"lines": validated})


def validate_update_transfer_payload(payload: TransferUpdateRequest | Mapping[str, Any]) -> TransferUpdateRequest:
    data = _coerce_model(payload, TransferUpdateRequest, None)
    if data.origin_store_id and data.destination_store_id and data.origin_store_id == data.destination_store_id:
        _raise_issue(None, "origin_store_id", "origin_store_id and destination_store_id must differ")
    if data.lines is not None:
        if not data.lines:
            _raise_issue(None, "lines", "lines must not be empty")
        validated = [validate_transfer_line(line, idx) for idx, line in enumerate(data.lines)]
        data = data.model_copy(update={"lines": validated})
    return data


def validate_dispatch_payload(payload: DispatchRequest | Mapping[str, Any]) -> DispatchRequest:
    data = _coerce_model(payload, DispatchRequest, None)
    return data


def validate_receive_payload(
    payload: ReceiveRequest | Mapping[str, Any],
    line_expectations: Mapping[str, int] | None = None,
    line_types: Mapping[str, str] | None = None,
) -> ReceiveRequest:
    data = _coerce_model(payload, ReceiveRequest, None)
    if not data.receive_lines:
        _raise_issue(None, "receive_lines", "receive_lines must not be empty")
    validated_lines = [
        _validate_receive_line(line, idx, line_expectations=line_expectations, line_types=line_types)
        for idx, line in enumerate(data.receive_lines)
    ]
    return data.model_copy(update={"receive_lines": validated_lines})


def validate_shortage_report_payload(
    payload: ReportShortagesRequest | Mapping[str, Any],
    line_expectations: Mapping[str, int] | None = None,
    line_types: Mapping[str, str] | None = None,
) -> ReportShortagesRequest:
    data = _coerce_model(payload, ReportShortagesRequest, None)
    if not data.shortages:
        _raise_issue(None, "shortages", "shortages must not be empty")
    validated_lines = [
        _validate_shortage_line(line, idx, line_expectations=line_expectations, line_types=line_types)
        for idx, line in enumerate(data.shortages)
    ]
    return data.model_copy(update={"shortages": validated_lines})


def validate_shortage_resolution_payload(
    payload: ResolveShortagesRequest | Mapping[str, Any],
    line_expectations: Mapping[str, int] | None = None,
    line_types: Mapping[str, str] | None = None,
    allow_lost_in_route: bool = True,
) -> ResolveShortagesRequest:
    data = _coerce_model(payload, ResolveShortagesRequest, None)
    if not data.resolution:
        _raise_issue(None, "resolution", "resolution is required")
    resolution = _coerce_model(data.resolution, TransferShortageResolution, None)
    if not resolution.lines:
        _raise_issue(None, "resolution.lines", "resolution lines must not be empty")
    if resolution.resolution == "LOST_IN_ROUTE" and not allow_lost_in_route:
        _raise_issue(None, "resolution.resolution", "LOST_IN_ROUTE requires manager permissions")
    validated_lines = [
        _validate_resolution_line(
            line,
            idx,
            line_expectations=line_expectations,
            line_types=line_types,
        )
        for idx, line in enumerate(resolution.lines)
    ]
    return data.model_copy(update={"resolution": resolution.model_copy(update={"lines": validated_lines})})


def validate_cancel_payload(payload: CancelRequest | Mapping[str, Any]) -> CancelRequest:
    data = _coerce_model(payload, CancelRequest, None)
    return data


def validate_transfer_line(line: TransferLineCreate | Mapping[str, Any], row_index: int) -> TransferLineCreate:
    data = _coerce_model(line, TransferLineCreate, row_index)
    if data.qty < 1:
        _raise_issue(row_index, "qty", "qty must be at least 1")
    if data.line_type == "EPC":
        if data.qty != 1:
            _raise_issue(row_index, "qty", "qty must be 1 for EPC lines")
        if not data.snapshot.epc:
            _raise_issue(row_index, "snapshot.epc", "epc is required for EPC lines")
    if data.line_type == "SKU" and data.snapshot.epc is not None:
        _raise_issue(row_index, "snapshot.epc", "epc must be empty for SKU lines")
    if not data.snapshot.location_code or not data.snapshot.pool:
        _raise_issue(row_index, "snapshot", "location_code and pool are required in snapshot")
    return data


def _validate_receive_line(
    line: TransferReceiveLine | Mapping[str, Any],
    row_index: int,
    *,
    line_expectations: Mapping[str, int] | None = None,
    line_types: Mapping[str, str] | None = None,
) -> TransferReceiveLine:
    data = _coerce_model(line, TransferReceiveLine, row_index)
    if data.qty < 1:
        _raise_issue(row_index, "qty", "qty must be at least 1")
    if not data.location_code or not data.pool:
        _raise_issue(row_index, "location_code", "location_code and pool are required")
    _validate_qty_against_expectations(data.line_id, data.qty, row_index, line_expectations, line_types)
    return data


def _validate_shortage_line(
    line: TransferShortageLine | Mapping[str, Any],
    row_index: int,
    *,
    line_expectations: Mapping[str, int] | None = None,
    line_types: Mapping[str, str] | None = None,
) -> TransferShortageLine:
    data = _coerce_model(line, TransferShortageLine, row_index)
    if data.qty < 1:
        _raise_issue(row_index, "qty", "qty must be at least 1")
    if not data.reason_code:
        _raise_issue(row_index, "reason_code", "reason_code is required")
    _validate_qty_against_expectations(data.line_id, data.qty, row_index, line_expectations, line_types)
    return data


def _validate_resolution_line(
    line: TransferShortageResolutionLine | Mapping[str, Any],
    row_index: int,
    *,
    line_expectations: Mapping[str, int] | None = None,
    line_types: Mapping[str, str] | None = None,
) -> TransferShortageResolutionLine:
    data = _coerce_model(line, TransferShortageResolutionLine, row_index)
    if data.qty < 1:
        _raise_issue(row_index, "qty", "qty must be at least 1")
    _validate_qty_against_expectations(data.line_id, data.qty, row_index, line_expectations, line_types)
    return data


def _validate_qty_against_expectations(
    line_id: str,
    qty: int,
    row_index: int,
    line_expectations: Mapping[str, int] | None,
    line_types: Mapping[str, str] | None,
) -> None:
    if line_types:
        line_type = line_types.get(line_id)
        if line_type == "EPC" and qty != 1:
            _raise_issue(row_index, "qty", "qty must be 1 for EPC lines")
    if line_expectations is not None:
        expected = line_expectations.get(line_id)
        if expected is None:
            _raise_issue(row_index, "line_id", "line_id not found in transfer lines")
        if qty > expected:
            _raise_issue(row_index, "qty", "qty cannot exceed outstanding quantity")


def _coerce_model(line: T | Mapping[str, Any], model_type: type[T], row_index: int | None) -> T:
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
