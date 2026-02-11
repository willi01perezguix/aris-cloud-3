from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping

from aris3_client_sdk import (
    ApiSession,
    PosCashSessionActionRequest,
    PosCashSessionCurrentResponse,
    PosCashSessionSummary,
    new_idempotency_keys,
    to_user_facing_error,
    validate_cash_in_payload,
    validate_cash_out_payload,
    validate_close_session_payload,
    validate_open_session_payload,
)
from aris3_client_sdk.exceptions import ApiError


@dataclass(frozen=True)
class PosCashMutationMeta:
    transaction_id: str
    idempotency_key: str


@dataclass(frozen=True)
class PosCashServiceError(RuntimeError):
    message: str
    details: str | None = None
    trace_id: str | None = None

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class PosCashMutationResult:
    response: PosCashSessionSummary
    meta: PosCashMutationMeta


class PosCashService:
    def __init__(self, session: ApiSession) -> None:
        self.session = session

    def current_session(self, *, store_id: str | None = None, tenant_id: str | None = None) -> PosCashSessionCurrentResponse:
        try:
            return self.session.pos_cash_client().get_current_session(store_id=store_id, tenant_id=tenant_id)
        except Exception as exc:
            raise self._normalize_error(exc) from exc

    def movements(self, **filters: Any):
        try:
            return self.session.pos_cash_client().get_movements(**filters)
        except Exception as exc:
            raise self._normalize_error(exc) from exc

    def open_session(
        self,
        payload: Mapping[str, Any],
        transaction_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> PosCashMutationResult:
        check = validate_open_session_payload(
            store_id=payload.get("store_id"),
            opening_amount=Decimal(str(payload.get("opening_amount"))) if payload.get("opening_amount") is not None else None,
            business_date=payload.get("business_date"),
            timezone=payload.get("timezone"),
        )
        if not check.ok:
            raise PosCashServiceError(message=self._issues_text(check.issues))
        return self._action("OPEN", payload, transaction_id, idempotency_key)

    def cash_in(self, payload: Mapping[str, Any], transaction_id: str | None = None, idempotency_key: str | None = None) -> PosCashMutationResult:
        check = validate_cash_in_payload(
            Decimal(str(payload.get("amount"))) if payload.get("amount") is not None else None,
            payload.get("reason"),
        )
        if not check.ok:
            raise PosCashServiceError(message=self._issues_text(check.issues))
        return self._action("CASH_IN", payload, transaction_id, idempotency_key)

    def cash_out(self, payload: Mapping[str, Any], transaction_id: str | None = None, idempotency_key: str | None = None) -> PosCashMutationResult:
        check = validate_cash_out_payload(
            Decimal(str(payload.get("amount"))) if payload.get("amount") is not None else None,
            payload.get("reason"),
        )
        if not check.ok:
            raise PosCashServiceError(message=self._issues_text(check.issues))
        return self._action("CASH_OUT", payload, transaction_id, idempotency_key)

    def close_session(self, payload: Mapping[str, Any], transaction_id: str | None = None, idempotency_key: str | None = None) -> PosCashMutationResult:
        check = validate_close_session_payload(
            Decimal(str(payload.get("counted_cash"))) if payload.get("counted_cash") is not None else None,
            payload.get("reason"),
        )
        if not check.ok:
            raise PosCashServiceError(message=self._issues_text(check.issues))
        return self._action("CLOSE", payload, transaction_id, idempotency_key)

    def _action(
        self,
        action: str,
        payload: Mapping[str, Any],
        transaction_id: str | None,
        idempotency_key: str | None,
    ) -> PosCashMutationResult:
        meta = self._mutation_meta(transaction_id, idempotency_key)
        request = PosCashSessionActionRequest.model_validate(
            {**payload, "action": action, "transaction_id": meta.transaction_id}
        )
        try:
            response = self.session.pos_cash_client().cash_action(
                action,
                request,
                transaction_id=meta.transaction_id,
                idempotency_key=meta.idempotency_key,
            )
            return PosCashMutationResult(response=response, meta=meta)
        except Exception as exc:
            raise self._normalize_error(exc) from exc

    @staticmethod
    def _issues_text(issues: list[Any]) -> str:
        return "; ".join(f"{issue.field}: {issue.reason}" for issue in issues)

    @staticmethod
    def _mutation_meta(transaction_id: str | None, idempotency_key: str | None) -> PosCashMutationMeta:
        if transaction_id and idempotency_key:
            return PosCashMutationMeta(transaction_id=transaction_id, idempotency_key=idempotency_key)
        keys = new_idempotency_keys()
        return PosCashMutationMeta(
            transaction_id=transaction_id or keys.transaction_id,
            idempotency_key=idempotency_key or keys.idempotency_key,
        )

    @staticmethod
    def _normalize_error(exc: Exception) -> PosCashServiceError:
        if isinstance(exc, PosCashServiceError):
            return exc
        if isinstance(exc, ApiError):
            return PosCashServiceError(
                message=getattr(to_user_facing_error(exc), "message", str(to_user_facing_error(exc))),
                details=str(exc.details) if exc.details is not None else None,
                trace_id=exc.trace_id,
            )
        return PosCashServiceError(message=str(exc) or "POS cash client error")
