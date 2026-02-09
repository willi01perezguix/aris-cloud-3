from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..exceptions import (
    ApiError,
    CashDrawerNegativeError,
    CashPermissionDeniedError,
    CashSessionNotOpenError,
)
from ..idempotency import IdempotencyKeys, new_idempotency_keys
from ..models_pos_cash import (
    PosCashDayCloseActionRequest,
    PosCashDayCloseResponse,
    PosCashMovementListResponse,
    PosCashSessionActionRequest,
    PosCashSessionCurrentResponse,
    PosCashSessionSummary,
)
from .base import BaseClient


@dataclass
class PosCashClient(BaseClient):
    def get_current_session(
        self,
        *,
        store_id: str | None = None,
        cashier_user_id: str | None = None,
        tenant_id: str | None = None,
    ) -> PosCashSessionCurrentResponse:
        params = {key: value for key, value in {
            "store_id": store_id,
            "cashier_user_id": cashier_user_id,
            "tenant_id": tenant_id,
        }.items() if value is not None}
        try:
            data = self._request("GET", "/aris3/pos/cash/session/current", params=params or None)
        except ApiError as exc:
            raise _map_cash_error(exc) from exc
        if not isinstance(data, dict):
            raise ValueError("Expected current cash session response to be a JSON object")
        return PosCashSessionCurrentResponse.model_validate(data)

    def cash_action(
        self,
        action: str,
        payload: PosCashSessionActionRequest | Mapping[str, Any],
        transaction_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> PosCashSessionSummary:
        request = _coerce_model(payload, PosCashSessionActionRequest)
        keys = _resolve_idempotency(transaction_id or request.transaction_id, idempotency_key)
        request = request.model_copy(update={"transaction_id": keys.transaction_id, "action": action})
        try:
            data = self._request(
                "POST",
                "/aris3/pos/cash/session/actions",
                json_body=request.model_dump(mode="json", exclude_none=True),
                headers={"Idempotency-Key": keys.idempotency_key},
            )
        except ApiError as exc:
            raise _map_cash_error(exc) from exc
        if not isinstance(data, dict):
            raise ValueError("Expected cash session response to be a JSON object")
        return PosCashSessionSummary.model_validate(data)

    def get_movements(
        self,
        *,
        store_id: str | None = None,
        cashier_user_id: str | None = None,
        movement_type: str | None = None,
        from_ts: str | None = None,
        to_ts: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        tenant_id: str | None = None,
    ) -> PosCashMovementListResponse:
        params = {key: value for key, value in {
            "store_id": store_id,
            "cashier_user_id": cashier_user_id,
            "movement_type": movement_type,
            "from_ts": from_ts,
            "to_ts": to_ts,
            "limit": limit,
            "offset": offset,
            "tenant_id": tenant_id,
        }.items() if value is not None}
        try:
            data = self._request("GET", "/aris3/pos/cash/movements", params=params or None)
        except ApiError as exc:
            raise _map_cash_error(exc) from exc
        if not isinstance(data, dict):
            raise ValueError("Expected cash movements response to be a JSON object")
        return PosCashMovementListResponse.model_validate(data)

    def day_close(
        self,
        payload: PosCashDayCloseActionRequest | Mapping[str, Any],
        transaction_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> PosCashDayCloseResponse:
        request = _coerce_model(payload, PosCashDayCloseActionRequest)
        keys = _resolve_idempotency(transaction_id or request.transaction_id, idempotency_key)
        request = request.model_copy(update={"transaction_id": keys.transaction_id, "action": "CLOSE_DAY"})
        try:
            data = self._request(
                "POST",
                "/aris3/pos/cash/day-close/actions",
                json_body=request.model_dump(mode="json", exclude_none=True),
                headers={"Idempotency-Key": keys.idempotency_key},
            )
        except ApiError as exc:
            raise _map_cash_error(exc) from exc
        if not isinstance(data, dict):
            raise ValueError("Expected cash day close response to be a JSON object")
        return PosCashDayCloseResponse.model_validate(data)


def _resolve_idempotency(transaction_id: str | None, idempotency_key: str | None) -> IdempotencyKeys:
    if transaction_id and idempotency_key:
        return IdempotencyKeys(transaction_id=transaction_id, idempotency_key=idempotency_key)
    generated = new_idempotency_keys()
    return IdempotencyKeys(
        transaction_id=transaction_id or generated.transaction_id,
        idempotency_key=idempotency_key or generated.idempotency_key,
    )


def _coerce_model(value: Any, model_type: type[Any]):
    if isinstance(value, model_type):
        return value
    return model_type.model_validate(value)


def _map_cash_error(exc: ApiError) -> ApiError:
    detail_message = ""
    if isinstance(exc.details, dict):
        detail_message = str(exc.details.get("message") or "")
    elif exc.details is not None:
        detail_message = str(exc.details)
    combined = f"{exc.message} {detail_message}".lower()
    if exc.code == "PERMISSION_DENIED" or exc.status_code == 403:
        return CashPermissionDeniedError(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            trace_id=exc.trace_id,
            status_code=exc.status_code,
        )
    if "open cash session required" in combined or "cash session is not open" in combined:
        return CashSessionNotOpenError(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            trace_id=exc.trace_id,
            status_code=exc.status_code,
        )
    if "negative expected balance" in combined:
        return CashDrawerNegativeError(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            trace_id=exc.trace_id,
            status_code=exc.status_code,
        )
    return exc
