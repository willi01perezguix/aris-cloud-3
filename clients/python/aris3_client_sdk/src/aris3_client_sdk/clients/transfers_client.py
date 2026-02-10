from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..exceptions import (
    ApiError,
    ForbiddenError,
    TransferActionForbiddenError,
    TransferStateError,
    TransferTenantMismatchError,
    ValidationError,
)
from ..idempotency import IdempotencyKeys, new_idempotency_keys
from ..models_transfers import (
    CancelRequest,
    DispatchRequest,
    ReceiveRequest,
    ReportShortagesRequest,
    ResolveShortagesRequest,
    TransferActionRequest,
    TransferCreateRequest,
    TransferListResponse,
    TransferQuery,
    TransferResponse,
    TransferUpdateRequest,
)
from ..transfer_validation import (
    ClientValidationError,
    ValidationIssue,
    validate_cancel_payload,
    validate_create_transfer_payload,
    validate_dispatch_payload,
    validate_receive_payload,
    validate_shortage_report_payload,
    validate_shortage_resolution_payload,
    validate_update_transfer_payload,
)
from .base import BaseClient


@dataclass
class TransfersClient(BaseClient):
    def list_transfers(self, filters: TransferQuery | None = None) -> TransferListResponse:
        params = build_transfer_params(filters or TransferQuery())
        payload = self._request("GET", "/aris3/transfers", params=params)
        if not isinstance(payload, dict):
            raise ValueError("Expected transfers response to be a JSON object")
        return TransferListResponse.model_validate(payload)

    def create_transfer(
        self,
        payload: TransferCreateRequest | Mapping[str, Any],
        transaction_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> TransferResponse:
        normalized = validate_create_transfer_payload(payload)
        keys = _resolve_idempotency(transaction_id, idempotency_key)
        request_payload = normalized.model_copy(update={"transaction_id": keys.transaction_id})
        try:
            data = self._request(
                "POST",
                "/aris3/transfers",
                json_body=request_payload.model_dump(mode="json", exclude_none=True),
                headers={"Idempotency-Key": keys.idempotency_key},
            )
        except ApiError as exc:
            _raise_transfer_error(exc)
        if not isinstance(data, dict):
            raise ValueError("Expected create transfer response to be a JSON object")
        return TransferResponse.model_validate(data)

    def update_transfer(
        self,
        transfer_id: str,
        payload: TransferUpdateRequest | Mapping[str, Any],
        transaction_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> TransferResponse:
        normalized = validate_update_transfer_payload(payload)
        keys = _resolve_idempotency(transaction_id, idempotency_key)
        request_payload = normalized.model_copy(update={"transaction_id": keys.transaction_id})
        try:
            data = self._request(
                "PATCH",
                f"/aris3/transfers/{transfer_id}",
                json_body=request_payload.model_dump(mode="json", exclude_none=True),
                headers={"Idempotency-Key": keys.idempotency_key},
            )
        except ApiError as exc:
            _raise_transfer_error(exc)
        if not isinstance(data, dict):
            raise ValueError("Expected update transfer response to be a JSON object")
        return TransferResponse.model_validate(data)

    def get_transfer(self, transfer_id: str) -> TransferResponse:
        try:
            payload = self._request("GET", f"/aris3/transfers/{transfer_id}")
        except ApiError as exc:
            _raise_transfer_error(exc)
        if not isinstance(payload, dict):
            raise ValueError("Expected transfer response to be a JSON object")
        return TransferResponse.model_validate(payload)

    def transfer_action(
        self,
        transfer_id: str,
        action: str,
        payload: TransferActionRequest | Mapping[str, Any] | None,
        transaction_id: str | None = None,
        idempotency_key: str | None = None,
        *,
        line_expectations: Mapping[str, int] | None = None,
        line_types: Mapping[str, str] | None = None,
        allow_lost_in_route: bool = True,
    ) -> TransferResponse:
        action_lower = action.lower()
        request_payload = _build_action_payload(
            action_lower,
            payload,
            line_expectations=line_expectations,
            line_types=line_types,
            allow_lost_in_route=allow_lost_in_route,
        )
        keys = _resolve_idempotency(transaction_id, idempotency_key)
        request_payload = request_payload.model_copy(update={"transaction_id": keys.transaction_id})
        try:
            data = self._request(
                "POST",
                f"/aris3/transfers/{transfer_id}/actions",
                json_body=request_payload.model_dump(mode="json", exclude_none=True),
                headers={"Idempotency-Key": keys.idempotency_key},
            )
        except ApiError as exc:
            _raise_transfer_error(exc)
        if not isinstance(data, dict):
            raise ValueError("Expected transfer action response to be a JSON object")
        return TransferResponse.model_validate(data)


def build_transfer_params(filters: TransferQuery) -> dict[str, Any]:
    return filters.model_dump(by_alias=True, exclude_none=True, mode="json")


def _resolve_idempotency(transaction_id: str | None, idempotency_key: str | None) -> IdempotencyKeys:
    if transaction_id and idempotency_key:
        return IdempotencyKeys(transaction_id=transaction_id, idempotency_key=idempotency_key)
    generated = new_idempotency_keys()
    return IdempotencyKeys(
        transaction_id=transaction_id or generated.transaction_id,
        idempotency_key=idempotency_key or generated.idempotency_key,
    )


def _build_action_payload(
    action: str,
    payload: TransferActionRequest | Mapping[str, Any] | None,
    *,
    line_expectations: Mapping[str, int] | None,
    line_types: Mapping[str, str] | None,
    allow_lost_in_route: bool,
) -> TransferActionRequest:
    if payload is None:
        raw_payload: Mapping[str, Any] = {"action": action}
    elif hasattr(payload, "model_dump"):
        raw_payload = payload.model_dump(mode="json", exclude_none=True)
    else:
        raw_payload = payload
    if action == "dispatch":
        return validate_dispatch_payload(raw_payload)
    if action == "receive":
        return validate_receive_payload(raw_payload, line_expectations=line_expectations, line_types=line_types)
    if action == "report_shortages":
        return validate_shortage_report_payload(raw_payload, line_expectations=line_expectations, line_types=line_types)
    if action == "resolve_shortages":
        return validate_shortage_resolution_payload(
            raw_payload,
            line_expectations=line_expectations,
            line_types=line_types,
            allow_lost_in_route=allow_lost_in_route,
        )
    if action == "cancel":
        return validate_cancel_payload(raw_payload)
    raise ClientValidationError([ValidationIssue(row_index=None, field="action", reason="unsupported action")])


def _raise_transfer_error(exc: ApiError) -> None:
    if isinstance(exc, ForbiddenError):
        if exc.code in {"CROSS_TENANT_ACCESS_DENIED", "STORE_SCOPE_MISMATCH"}:
            raise TransferTenantMismatchError(**exc.__dict__) from exc
        if exc.code == "PERMISSION_DENIED":
            raise TransferActionForbiddenError(**exc.__dict__) from exc
    if isinstance(exc, ValidationError):
        message = _detail_message(exc)
        if message and "state" in message:
            raise TransferStateError(**exc.__dict__) from exc
        if message and "destination" in message:
            raise TransferActionForbiddenError(**exc.__dict__) from exc
    raise exc


def _detail_message(exc: ApiError) -> str | None:
    if isinstance(exc.details, dict):
        message = exc.details.get("message")
        if isinstance(message, str):
            return message.lower()
    if exc.message:
        return exc.message.lower()
    return None
