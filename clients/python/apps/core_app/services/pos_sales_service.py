from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping, Sequence

from aris3_client_sdk import (
    ApiSession,
    PosSaleActionRequest,
    PosSaleCreateRequest,
    PosSaleLineCreate,
    PosSaleQuery,
    PosSaleResponse,
    PosSaleUpdateRequest,
    compute_payment_totals,
    new_idempotency_keys,
    to_user_facing_error,
    validate_checkout_payload,
)
from aris3_client_sdk.exceptions import ApiError


@dataclass(frozen=True)
class PosMutationMeta:
    transaction_id: str
    idempotency_key: str


@dataclass(frozen=True)
class PosSalesServiceError(RuntimeError):
    message: str
    details: str | None = None
    trace_id: str | None = None

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class PosSalesMutationResult:
    response: PosSaleResponse
    meta: PosMutationMeta


class PosSalesService:
    def __init__(self, session: ApiSession) -> None:
        self.session = session

    def create_draft(
        self,
        *,
        store_id: str,
        lines: Sequence[PosSaleLineCreate | Mapping[str, Any]],
        tenant_id: str | None = None,
        transaction_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> PosSalesMutationResult:
        meta = self._mutation_meta(transaction_id, idempotency_key)
        payload = PosSaleCreateRequest(
            store_id=store_id,
            tenant_id=tenant_id,
            transaction_id=meta.transaction_id,
            lines=[self._line_model(line) for line in lines],
        )
        try:
            response = self.session.pos_sales_client().create_sale(
                payload,
                transaction_id=meta.transaction_id,
                idempotency_key=meta.idempotency_key,
            )
            return PosSalesMutationResult(response=response, meta=meta)
        except Exception as exc:
            raise self._normalize_error(exc) from exc

    def update_draft(
        self,
        *,
        sale_id: str,
        lines: Sequence[PosSaleLineCreate | Mapping[str, Any]],
        tenant_id: str | None = None,
        transaction_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> PosSalesMutationResult:
        meta = self._mutation_meta(transaction_id, idempotency_key)
        payload = PosSaleUpdateRequest(
            tenant_id=tenant_id,
            transaction_id=meta.transaction_id,
            lines=[self._line_model(line) for line in lines],
        )
        try:
            response = self.session.pos_sales_client().update_sale(
                sale_id,
                payload,
                transaction_id=meta.transaction_id,
                idempotency_key=meta.idempotency_key,
            )
            return PosSalesMutationResult(response=response, meta=meta)
        except Exception as exc:
            raise self._normalize_error(exc) from exc

    def get_sale(self, sale_id: str) -> PosSaleResponse:
        try:
            return self.session.pos_sales_client().get_sale(sale_id)
        except Exception as exc:
            raise self._normalize_error(exc) from exc

    def list_sales(self, filters: PosSaleQuery | Mapping[str, Any] | None = None):
        query = None
        if filters is not None:
            query = filters if isinstance(filters, PosSaleQuery) else PosSaleQuery.model_validate(filters)
        try:
            return self.session.pos_sales_client().list_sales(query)
        except Exception as exc:
            raise self._normalize_error(exc) from exc

    def checkout(
        self,
        sale_id: str,
        *,
        payments: Sequence[Mapping[str, Any]],
        total_due: Decimal | float | str,
        tenant_id: str | None = None,
        transaction_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> PosSalesMutationResult:
        validation = validate_checkout_payload(total_due=total_due, payments=payments)
        if not validation.ok:
            reason = "; ".join(f"{issue.field}: {issue.reason}" for issue in validation.issues)
            raise PosSalesServiceError(message=f"Checkout validation failed: {reason}")
        meta = self._mutation_meta(transaction_id, idempotency_key)
        request = PosSaleActionRequest(
            action="checkout",
            tenant_id=tenant_id,
            transaction_id=meta.transaction_id,
            payments=validation.payments,
        )
        try:
            response = self.session.pos_sales_client().sale_action(
                sale_id,
                action="checkout",
                payload=request,
                transaction_id=meta.transaction_id,
                idempotency_key=meta.idempotency_key,
            )
            return PosSalesMutationResult(response=response, meta=meta)
        except Exception as exc:
            raise self._normalize_error(exc) from exc

    def cancel(
        self,
        sale_id: str,
        *,
        tenant_id: str | None = None,
        transaction_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> PosSalesMutationResult:
        meta = self._mutation_meta(transaction_id, idempotency_key)
        request = PosSaleActionRequest(action="cancel", tenant_id=tenant_id, transaction_id=meta.transaction_id)
        try:
            response = self.session.pos_sales_client().sale_action(
                sale_id,
                action="cancel",
                payload=request,
                transaction_id=meta.transaction_id,
                idempotency_key=meta.idempotency_key,
            )
            return PosSalesMutationResult(response=response, meta=meta)
        except Exception as exc:
            raise self._normalize_error(exc) from exc

    @staticmethod
    def payment_totals(total_due: Decimal | str | float, payments: Sequence[Mapping[str, Any]]) -> dict[str, Decimal]:
        normalized = validate_checkout_payload(total_due=total_due, payments=payments).payments
        totals = compute_payment_totals(Decimal(str(total_due)), normalized)
        return {
            "total_due": totals.total_due,
            "paid_total": totals.paid_total,
            "missing_amount": totals.missing_amount,
            "change_amount": totals.change_due,
            "cash_total": totals.cash_total,
        }

    @staticmethod
    def _line_model(line: PosSaleLineCreate | Mapping[str, Any]) -> PosSaleLineCreate:
        return line if isinstance(line, PosSaleLineCreate) else PosSaleLineCreate.model_validate(line)

    @staticmethod
    def _mutation_meta(transaction_id: str | None, idempotency_key: str | None) -> PosMutationMeta:
        if transaction_id and idempotency_key:
            return PosMutationMeta(transaction_id=transaction_id, idempotency_key=idempotency_key)
        keys = new_idempotency_keys()
        return PosMutationMeta(
            transaction_id=transaction_id or keys.transaction_id,
            idempotency_key=idempotency_key or keys.idempotency_key,
        )

    @staticmethod
    def _normalize_error(exc: Exception) -> PosSalesServiceError:
        if isinstance(exc, PosSalesServiceError):
            return exc
        if isinstance(exc, ApiError):
            return PosSalesServiceError(
                message=getattr(to_user_facing_error(exc), "message", str(to_user_facing_error(exc))),
                details=str(exc.details) if exc.details is not None else None,
                trace_id=exc.trace_id,
            )
        return PosSalesServiceError(message=str(exc) or "POS sales client error")
