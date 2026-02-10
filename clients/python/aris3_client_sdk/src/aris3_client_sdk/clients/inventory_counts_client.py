from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..exceptions import (
    ApiError,
    ForbiddenError,
    InventoryCountActionForbiddenError,
    InventoryCountClosedError,
    InventoryCountLockConflictError,
    InventoryCountStateError,
    ValidationError,
)
from ..idempotency import IdempotencyKeys, new_idempotency_keys
from ..inventory_counts_validation import (
    validate_action_state_intent,
    validate_reconcile_payload,
    validate_scan_batch_payload,
    validate_start_payload,
)
from ..models_inventory_counts import (
    CountActionRequest,
    CountCreateRequest,
    CountDifferencesResponse,
    CountExportResponse,
    CountHeader,
    CountListResponse,
    CountQuery,
    CountSummary,
    ReconcileRequest,
    ReconcileResponse,
    ScanBatchRequest,
    ScanBatchResponse,
)
from .base import BaseClient


@dataclass
class InventoryCountsClient(BaseClient):
    def list_counts(self, filters: CountQuery | None = None) -> CountListResponse:
        params = (filters or CountQuery()).model_dump(by_alias=True, exclude_none=True, mode="json")
        payload = self._request("GET", "/aris3/inventory-counts", params=params)
        if not isinstance(payload, dict):
            raise ValueError("Expected count list response to be a JSON object")
        return CountListResponse.model_validate(payload)

    def create_or_start_count(
        self,
        payload: CountCreateRequest | Mapping[str, Any],
        transaction_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> CountHeader:
        normalized = validate_start_payload(payload)
        keys = _resolve_idempotency(transaction_id, idempotency_key)
        request_payload = normalized.model_copy(update={"transaction_id": keys.transaction_id})
        try:
            data = self._request(
                "POST",
                "/aris3/inventory-counts",
                json_body=request_payload.model_dump(mode="json", exclude_none=True),
                headers={"Idempotency-Key": keys.idempotency_key},
            )
        except ApiError as exc:
            _raise_inventory_error(exc)
        if not isinstance(data, dict):
            raise ValueError("Expected count create response to be a JSON object")
        return CountHeader.model_validate(data.get("header") or data)

    def get_count(self, count_id: str) -> CountHeader:
        payload = self._request("GET", f"/aris3/inventory-counts/{count_id}")
        if not isinstance(payload, dict):
            raise ValueError("Expected count response to be a JSON object")
        return CountHeader.model_validate(payload.get("header") or payload)

    def count_action(
        self,
        count_id: str,
        action: str,
        payload: CountActionRequest | Mapping[str, Any] | None,
        transaction_id: str | None = None,
        idempotency_key: str | None = None,
        *,
        current_state: str | None = None,
    ) -> CountHeader:
        if current_state:
            validate_action_state_intent(current_state, action)

        raw_payload = {"action": action.upper()}
        if payload is not None:
            if isinstance(payload, CountActionRequest):
                raw_payload.update(payload.model_dump(mode="json", exclude_none=True))
            else:
                raw_payload.update(dict(payload))

        request_model = CountActionRequest.model_validate(raw_payload)
        keys = _resolve_idempotency(transaction_id, idempotency_key)
        request_model = request_model.model_copy(update={"transaction_id": keys.transaction_id})
        try:
            data = self._request(
                "POST",
                f"/aris3/inventory-counts/{count_id}/actions",
                json_body=request_model.model_dump(mode="json", exclude_none=True),
                headers={"Idempotency-Key": keys.idempotency_key},
            )
        except ApiError as exc:
            _raise_inventory_error(exc)
        if not isinstance(data, dict):
            raise ValueError("Expected count action response to be a JSON object")
        return CountHeader.model_validate(data.get("header") or data)

    def submit_scan_batch(
        self,
        count_id: str,
        payload: ScanBatchRequest | Mapping[str, Any],
        transaction_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> ScanBatchResponse:
        normalized = validate_scan_batch_payload(payload)
        keys = _resolve_idempotency(transaction_id, idempotency_key)
        request_payload = normalized.model_copy(update={"transaction_id": keys.transaction_id})
        try:
            data = self._request(
                "POST",
                f"/aris3/inventory-counts/{count_id}/scan-batches",
                json_body=request_payload.model_dump(mode="json", exclude_none=True),
                headers={"Idempotency-Key": keys.idempotency_key},
            )
        except ApiError as exc:
            _raise_inventory_error(exc)
        if not isinstance(data, dict):
            raise ValueError("Expected scan batch response to be a JSON object")
        return ScanBatchResponse.model_validate(data)

    def get_count_summary(self, count_id: str) -> CountSummary:
        payload = self._request("GET", f"/aris3/inventory-counts/{count_id}/summary")
        if not isinstance(payload, dict):
            raise ValueError("Expected count summary response to be a JSON object")
        return CountSummary.model_validate(payload)

    def get_count_differences(self, count_id: str) -> CountDifferencesResponse:
        payload = self._request("GET", f"/aris3/inventory-counts/{count_id}/differences")
        if not isinstance(payload, dict):
            raise ValueError("Expected count differences response to be a JSON object")
        return CountDifferencesResponse.model_validate(payload)

    def reconcile_count(
        self,
        count_id: str,
        payload: ReconcileRequest | Mapping[str, Any] | None = None,
        transaction_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> ReconcileResponse:
        request = validate_reconcile_payload(payload)
        keys = _resolve_idempotency(transaction_id, idempotency_key)
        action_payload = request.model_copy(update={"transaction_id": keys.transaction_id})
        try:
            data = self._request(
                "POST",
                f"/aris3/inventory-counts/{count_id}/actions",
                json_body=action_payload.model_dump(mode="json", exclude_none=True),
                headers={"Idempotency-Key": keys.idempotency_key},
            )
        except ApiError as exc:
            _raise_inventory_error(exc)
        if not isinstance(data, dict):
            raise ValueError("Expected reconcile response to be a JSON object")
        return ReconcileResponse.model_validate(data)

    def export_count_result(self, count_id: str, export_format: str = "csv", **params: Any) -> CountExportResponse | None:
        query = {"format": export_format, **params}
        try:
            payload = self._request("GET", f"/aris3/inventory-counts/{count_id}/export", params=query)
        except ApiError as exc:
            if exc.status_code == 404:
                return None
            _raise_inventory_error(exc)
        if not isinstance(payload, dict):
            raise ValueError("Expected export response to be a JSON object")
        return CountExportResponse.model_validate(payload)


def _resolve_idempotency(transaction_id: str | None, idempotency_key: str | None) -> IdempotencyKeys:
    if transaction_id and idempotency_key:
        return IdempotencyKeys(transaction_id=transaction_id, idempotency_key=idempotency_key)
    generated = new_idempotency_keys()
    return IdempotencyKeys(
        transaction_id=transaction_id or generated.transaction_id,
        idempotency_key=idempotency_key or generated.idempotency_key,
    )


def _raise_inventory_error(exc: ApiError) -> None:
    message = _detail_message(exc)
    if isinstance(exc, ForbiddenError):
        raise InventoryCountActionForbiddenError(**exc.__dict__) from exc
    if isinstance(exc, ValidationError):
        if message and "lock" in message:
            raise InventoryCountLockConflictError(**exc.__dict__) from exc
        if message and ("state" in message or "transition" in message):
            raise InventoryCountStateError(**exc.__dict__) from exc
        if message and ("closed" in message or "stale" in message):
            raise InventoryCountClosedError(**exc.__dict__) from exc
    raise exc


def _detail_message(exc: ApiError) -> str | None:
    if isinstance(exc.details, dict):
        message = exc.details.get("message")
        if isinstance(message, str):
            return message.lower()
    if exc.message:
        return exc.message.lower()
    return None
