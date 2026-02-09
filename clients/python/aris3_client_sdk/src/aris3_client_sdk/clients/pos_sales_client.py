from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..idempotency import IdempotencyKeys, new_idempotency_keys
from ..models_pos_sales import (
    PosSaleActionRequest,
    PosSaleCreateRequest,
    PosSaleListResponse,
    PosSaleQuery,
    PosSaleResponse,
    PosSaleUpdateRequest,
)
from .base import BaseClient


@dataclass
class PosSalesClient(BaseClient):
    def create_sale(
        self,
        payload: PosSaleCreateRequest | Mapping[str, Any],
        transaction_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> PosSaleResponse:
        request = _coerce_model(payload, PosSaleCreateRequest)
        keys = _resolve_idempotency(transaction_id or request.transaction_id, idempotency_key)
        request = request.model_copy(update={"transaction_id": keys.transaction_id})
        data = self._request(
            "POST",
            "/aris3/pos/sales",
            json_body=request.model_dump(mode="json", exclude_none=True),
            headers={"Idempotency-Key": keys.idempotency_key},
        )
        if not isinstance(data, dict):
            raise ValueError("Expected create sale response to be a JSON object")
        return PosSaleResponse.model_validate(data)

    def update_sale(
        self,
        sale_id: str,
        payload: PosSaleUpdateRequest | Mapping[str, Any],
        transaction_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> PosSaleResponse:
        request = _coerce_model(payload, PosSaleUpdateRequest)
        keys = _resolve_idempotency(transaction_id or request.transaction_id, idempotency_key)
        request = request.model_copy(update={"transaction_id": keys.transaction_id})
        data = self._request(
            "PATCH",
            f"/aris3/pos/sales/{sale_id}",
            json_body=request.model_dump(mode="json", exclude_none=True),
            headers={"Idempotency-Key": keys.idempotency_key},
        )
        if not isinstance(data, dict):
            raise ValueError("Expected update sale response to be a JSON object")
        return PosSaleResponse.model_validate(data)

    def get_sale(self, sale_id: str) -> PosSaleResponse:
        data = self._request("GET", f"/aris3/pos/sales/{sale_id}")
        if not isinstance(data, dict):
            raise ValueError("Expected sale response to be a JSON object")
        return PosSaleResponse.model_validate(data)

    def list_sales(self, filters: PosSaleQuery | Mapping[str, Any] | None = None) -> PosSaleListResponse:
        params = None
        if filters is not None:
            query = _coerce_model(filters, PosSaleQuery)
            params = query.model_dump(by_alias=True, exclude_none=True, mode="json")
        data = self._request("GET", "/aris3/pos/sales", params=params)
        if not isinstance(data, dict):
            raise ValueError("Expected list sales response to be a JSON object")
        return PosSaleListResponse.model_validate(data)

    def sale_action(
        self,
        sale_id: str,
        action: str,
        payload: PosSaleActionRequest | Mapping[str, Any],
        transaction_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> PosSaleResponse:
        request = _coerce_model(payload, PosSaleActionRequest)
        keys = _resolve_idempotency(transaction_id or request.transaction_id, idempotency_key)
        request = request.model_copy(update={"transaction_id": keys.transaction_id, "action": action})
        data = self._request(
            "POST",
            f"/aris3/pos/sales/{sale_id}/actions",
            json_body=request.model_dump(mode="json", exclude_none=True),
            headers={"Idempotency-Key": keys.idempotency_key},
        )
        if not isinstance(data, dict):
            raise ValueError("Expected sale action response to be a JSON object")
        return PosSaleResponse.model_validate(data)


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
