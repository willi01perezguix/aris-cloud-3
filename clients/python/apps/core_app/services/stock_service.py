from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from aris3_client_sdk import ApiSession, new_idempotency_keys, to_user_facing_error
from aris3_client_sdk.exceptions import ApiError
from aris3_client_sdk.models_stock import (
    StockImportEpcLine,
    StockImportResponse,
    StockImportSkuLine,
    StockMigrateRequest,
    StockMigrateResponse,
    StockQuery,
    StockTableResponse,
)
from aris3_client_sdk.stock_validation import ClientValidationError


@dataclass(frozen=True)
class StockMutationMeta:
    transaction_id: str
    idempotency_key: str


@dataclass(frozen=True)
class StockServiceError(RuntimeError):
    message: str
    details: str | None = None
    trace_id: str | None = None

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class StockMutationResult:
    response: StockImportResponse | StockMigrateResponse
    meta: StockMutationMeta


class StockService:
    def __init__(self, session: ApiSession) -> None:
        self.session = session

    def query_stock(self, filters: Mapping[str, Any] | StockQuery) -> StockTableResponse:
        stock_query = filters if isinstance(filters, StockQuery) else StockQuery.model_validate(filters)
        try:
            return self.session.stock_client().get_stock(stock_query)
        except Exception as exc:
            raise self._normalize_error(exc) from exc

    def import_epc(
        self,
        lines: Sequence[StockImportEpcLine | Mapping[str, Any]],
        transaction_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> StockMutationResult:
        meta = self._mutation_meta(transaction_id, idempotency_key)
        try:
            response = self.session.stock_client().import_epc(
                lines,
                transaction_id=meta.transaction_id,
                idempotency_key=meta.idempotency_key,
            )
            return StockMutationResult(response=response, meta=meta)
        except Exception as exc:
            raise self._normalize_error(exc) from exc

    def import_sku(
        self,
        lines: Sequence[StockImportSkuLine | Mapping[str, Any]],
        transaction_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> StockMutationResult:
        meta = self._mutation_meta(transaction_id, idempotency_key)
        try:
            response = self.session.stock_client().import_sku(
                lines,
                transaction_id=meta.transaction_id,
                idempotency_key=meta.idempotency_key,
            )
            return StockMutationResult(response=response, meta=meta)
        except Exception as exc:
            raise self._normalize_error(exc) from exc

    def migrate_sku_to_epc(
        self,
        line: StockMigrateRequest | Mapping[str, Any],
        transaction_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> StockMutationResult:
        meta = self._mutation_meta(transaction_id, idempotency_key)
        payload = line if isinstance(line, StockMigrateRequest) else StockMigrateRequest.model_validate(line)
        try:
            response = self.session.stock_client().migrate_sku_to_epc(
                [payload],
                transaction_id=meta.transaction_id,
                idempotency_key=meta.idempotency_key,
            )
            return StockMutationResult(response=response, meta=meta)
        except Exception as exc:
            raise self._normalize_error(exc) from exc

    @staticmethod
    def _mutation_meta(transaction_id: str | None, idempotency_key: str | None) -> StockMutationMeta:
        generated = new_idempotency_keys()
        return StockMutationMeta(
            transaction_id=transaction_id or generated.transaction_id,
            idempotency_key=idempotency_key or generated.idempotency_key,
        )

    @staticmethod
    def _normalize_error(exc: Exception) -> StockServiceError:
        if isinstance(exc, StockServiceError):
            return exc
        if isinstance(exc, ApiError):
            user_facing = to_user_facing_error(exc)
            return StockServiceError(
                message=user_facing.message,
                details=user_facing.technical_details,
                trace_id=user_facing.trace_id,
            )
        if isinstance(exc, ClientValidationError):
            return StockServiceError(message=str(exc), details="CLIENT_VALIDATION")
        return StockServiceError(message=str(exc) or "Unexpected stock client error")
