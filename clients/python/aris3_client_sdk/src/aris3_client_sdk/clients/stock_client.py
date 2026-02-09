from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ..idempotency import IdempotencyKeys, new_idempotency_keys
from ..models_stock import (
    StockImportEpcLine,
    StockImportEpcRequest,
    StockImportResponse,
    StockImportSkuLine,
    StockImportSkuRequest,
    StockMigrateRequest,
    StockMigrateResponse,
    StockQuery,
    StockTableResponse,
)
from ..stock_validation import (
    ClientValidationError,
    ValidationIssue,
    validate_import_epc_line,
    validate_import_sku_line,
    validate_migration_line,
)
from .base import BaseClient


@dataclass
class StockClient(BaseClient):
    def get_stock(self, filters: StockQuery) -> StockTableResponse:
        params = build_stock_params(filters)
        payload = self._request("GET", "/aris3/stock", params=params)
        if not isinstance(payload, dict):
            raise ValueError("Expected stock query response to be a JSON object")
        return StockTableResponse.model_validate(payload)

    def import_epc(
        self,
        lines: Sequence[StockImportEpcLine | Mapping[str, Any]],
        transaction_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> StockImportResponse:
        if not lines:
            raise ClientValidationError([ValidationIssue(row_index=None, field="lines", reason="lines must not be empty")])
        normalized = [validate_import_epc_line(line, idx) for idx, line in enumerate(lines)]
        keys = _resolve_idempotency(transaction_id, idempotency_key)
        payload = StockImportEpcRequest(transaction_id=keys.transaction_id, lines=normalized)
        data = self._request(
            "POST",
            "/aris3/stock/import-epc",
            json_body=payload.model_dump(mode="json", exclude_none=True),
            headers={"Idempotency-Key": keys.idempotency_key},
        )
        if not isinstance(data, dict):
            raise ValueError("Expected import-epc response to be a JSON object")
        return StockImportResponse.model_validate(data)

    def import_sku(
        self,
        lines: Sequence[StockImportSkuLine | Mapping[str, Any]],
        transaction_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> StockImportResponse:
        if not lines:
            raise ClientValidationError([ValidationIssue(row_index=None, field="lines", reason="lines must not be empty")])
        normalized = [validate_import_sku_line(line, idx) for idx, line in enumerate(lines)]
        keys = _resolve_idempotency(transaction_id, idempotency_key)
        payload = StockImportSkuRequest(transaction_id=keys.transaction_id, lines=normalized)
        data = self._request(
            "POST",
            "/aris3/stock/import-sku",
            json_body=payload.model_dump(mode="json", exclude_none=True),
            headers={"Idempotency-Key": keys.idempotency_key},
        )
        if not isinstance(data, dict):
            raise ValueError("Expected import-sku response to be a JSON object")
        return StockImportResponse.model_validate(data)

    def migrate_sku_to_epc(
        self,
        lines: Sequence[StockMigrateRequest | Mapping[str, Any]],
        transaction_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> StockMigrateResponse:
        if not lines:
            raise ClientValidationError([ValidationIssue(row_index=None, field="lines", reason="lines must not be empty")])
        if len(lines) != 1:
            raise ClientValidationError(
                [ValidationIssue(row_index=None, field="lines", reason="only one migration payload is supported")]
            )
        payload_line = validate_migration_line(lines[0], row_index=0)
        keys = _resolve_idempotency(transaction_id, idempotency_key)
        payload = payload_line.model_copy(update={"transaction_id": keys.transaction_id})
        data = self._request(
            "POST",
            "/aris3/stock/migrate-sku-to-epc",
            json_body=payload.model_dump(mode="json", exclude_none=True),
            headers={"Idempotency-Key": keys.idempotency_key},
        )
        if not isinstance(data, dict):
            raise ValueError("Expected migrate-sku-to-epc response to be a JSON object")
        return StockMigrateResponse.model_validate(data)


def build_stock_params(filters: StockQuery) -> dict[str, Any]:
    return filters.model_dump(by_alias=True, exclude_none=True, mode="json")


def _resolve_idempotency(transaction_id: str | None, idempotency_key: str | None) -> IdempotencyKeys:
    if transaction_id and idempotency_key:
        return IdempotencyKeys(transaction_id=transaction_id, idempotency_key=idempotency_key)
    generated = new_idempotency_keys()
    return IdempotencyKeys(
        transaction_id=transaction_id or generated.transaction_id,
        idempotency_key=idempotency_key or generated.idempotency_key,
    )
