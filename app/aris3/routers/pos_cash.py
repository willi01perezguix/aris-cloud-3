from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import case, exists, func, select
from sqlalchemy.exc import IntegrityError

from app.aris3.core.deps import get_current_token_data, require_active_user, require_permission
from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.core.scope import DEFAULT_BROAD_STORE_ROLES, enforce_store_scope, enforce_tenant_scope, is_superadmin
from app.aris3.db.models import PosCashCut, PosCashDayClose, PosCashMovement, PosCashSession, PosPayment, PosSale
from app.aris3.db.session import get_db
from app.aris3.schemas.errors import ApiErrorResponse, ApiValidationErrorResponse
from app.aris3.schemas.pos_cash import (
    PosCashDayCloseActionRequest,
    PosCashCutActionRequest,
    PosCashCutCreateRequest,
    PosCashCutDetailResponse,
    PosCashCutListResponse,
    PosCashCutQuoteRequest,
    PosCashCutQuoteResponse,
    PosCashCutSummary,
    PosCashDayCloseResponse,
    PosCashDayCloseSummaryListResponse,
    PosCashDayCloseSummaryResponse,
    PosCashMovementListResponse,
    PosCashMovementResponse,
    PosCashReconciliationBreakdownResponse,
    PosCashReconciliationBreakdownRow,
    PosCashSessionActionRequest,
    PosCashSessionCurrentResponse,
    PosCashSessionSummary,
)
from app.aris3.services.audit import AuditEventPayload, AuditService
from app.aris3.services.idempotency import IdempotencyService, extract_idempotency_key


router = APIRouter()
logger = logging.getLogger(__name__)

POS_STANDARD_ERROR_RESPONSES = {
    401: {"description": "Unauthorized", "model": ApiErrorResponse},
    403: {"description": "Forbidden", "model": ApiErrorResponse},
    404: {"description": "Resource not found", "model": ApiErrorResponse},
    409: {"description": "Business conflict", "model": ApiErrorResponse},
    422: {"description": "Validation error", "model": ApiValidationErrorResponse},
}

POS_LIST_ERROR_RESPONSES = {
    401: {"description": "Unauthorized", "model": ApiErrorResponse},
    403: {"description": "Forbidden", "model": ApiErrorResponse},
    409: {"description": "Business conflict", "model": ApiErrorResponse},
    422: {"description": "Validation error", "model": ApiValidationErrorResponse},
}

CASH_ERROR_EXAMPLES = {
    "401": {"code": "UNAUTHORIZED", "message": "Authentication required", "details": {"message": "Missing bearer token"}, "trace_id": "trace-cash-401"},
    "403": {"code": "FORBIDDEN", "message": "You do not have access to this store", "details": {"required_permission": "POS_CASH_MANAGE"}, "trace_id": "trace-cash-403"},
    "404_session": {"code": "NOT_FOUND", "message": "cash session not found", "details": {"cash_session_id": "00000000-0000-0000-0000-000000009999"}, "trace_id": "trace-cash-404"},
    "409": {"code": "BUSINESS_CONFLICT", "message": "cash session already open", "details": {"store_id": "00000000-0000-0000-0000-000000000001"}, "trace_id": "trace-cash-409"},
}

_IDEMPOTENCY_REQUIRED_HEADER_PARAMETER = {
    "name": "Idempotency-Key",
    "in": "header",
    "required": True,
    "schema": {"type": "string"},
    "description": "Idempotency key required for mutation safety. Legacy alias X-Idempotency-Key is also accepted.",
}

MOVEMENT_TYPE_MAP = {
    "OPEN": "OPENING",
    "OPENING": "OPENING",
    "CASH_IN": "CASH_IN",
    "CASH_OUT": "CASH_OUT",
    "SALE": "SALE_CASH_IN",
    "SALE_CASH_IN": "SALE_CASH_IN",
    "CASH_OUT_REFUND": "CASH_OUT_REFUND",
    "CLOSE": "CLOSE_ADJUSTMENT",
    "CLOSE_ADJUSTMENT": "CLOSE_ADJUSTMENT",
    "DAY_CLOSE": "DAY_CLOSE",
}

RECONCILIATION_ACTIONS = {
    "OPENING",
    "CASH_IN",
    "CASH_OUT",
    "SALE_CASH_IN",
    "CASH_OUT_REFUND",
}


def _require_transaction_id(transaction_id: str | None) -> None:
    if not transaction_id:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "transaction_id is required"})


def _normalize_uuid(value: str | UUID) -> str:
    return str(value)


def _resolve_tenant_id(token_data, tenant_id: str | None) -> str:
    if is_superadmin(token_data.role):
        if not tenant_id:
            raise AppError(ErrorCatalog.TENANT_SCOPE_REQUIRED)
        return tenant_id
    if not token_data.tenant_id:
        raise AppError(ErrorCatalog.TENANT_SCOPE_REQUIRED)
    if tenant_id and tenant_id != token_data.tenant_id:
        raise AppError(ErrorCatalog.CROSS_TENANT_ACCESS_DENIED)
    return token_data.tenant_id


def _resolve_store_id(token_data, requested_store_id: str | None) -> str:
    broad_roles = {role.upper() for role in DEFAULT_BROAD_STORE_ROLES}
    if token_data.store_id and token_data.role.upper() not in broad_roles:
        if requested_store_id and requested_store_id != token_data.store_id:
            raise AppError(ErrorCatalog.STORE_SCOPE_MISMATCH)
        return token_data.store_id
    if requested_store_id:
        return requested_store_id
    if token_data.store_id:
        return token_data.store_id
    raise AppError(ErrorCatalog.STORE_SCOPE_REQUIRED)


def _session_summary(session: PosCashSession) -> PosCashSessionSummary:
    return PosCashSessionSummary(
        id=_normalize_uuid(session.id),
        tenant_id=_normalize_uuid(session.tenant_id),
        store_id=_normalize_uuid(session.store_id),
        cashier_user_id=_normalize_uuid(session.cashier_user_id),
        status=session.status,
        business_date=session.business_date,
        timezone=session.timezone,
        opening_amount=Decimal(str(session.opening_amount)),
        expected_cash=Decimal(str(session.expected_cash)),
        counted_cash=Decimal(str(session.counted_cash)) if session.counted_cash is not None else None,
        difference=Decimal(str(session.difference)) if session.difference is not None else None,
        opened_at=session.opened_at,
        closed_at=session.closed_at,
        created_at=session.created_at,
    )


def _movement_response(movement: PosCashMovement) -> PosCashMovementResponse:
    return PosCashMovementResponse(
        id=_normalize_uuid(movement.id),
        tenant_id=_normalize_uuid(movement.tenant_id),
        store_id=_normalize_uuid(movement.store_id),
        cashier_user_id=_normalize_uuid(movement.cashier_user_id),
        actor_user_id=_normalize_uuid(movement.actor_user_id) if movement.actor_user_id else None,
        cash_session_id=_normalize_uuid(movement.cash_session_id) if movement.cash_session_id else None,
        sale_id=_normalize_uuid(movement.sale_id) if movement.sale_id else None,
        business_date=movement.business_date,
        timezone=movement.timezone,
        movement_type=movement.action,
        amount=Decimal(str(movement.amount)),
        expected_balance_before=Decimal(str(movement.expected_balance_before))
        if movement.expected_balance_before is not None
        else None,
        expected_balance_after=Decimal(str(movement.expected_balance_after))
        if movement.expected_balance_after is not None
        else None,
        transaction_id=movement.transaction_id,
        reason=movement.reason,
        trace_id=movement.trace_id,
        occurred_at=movement.occurred_at,
        created_at=movement.created_at,
    )


def _normalize_movement_type(action: str) -> str:
    return MOVEMENT_TYPE_MAP.get(action, action)


def _difference_type(difference: Decimal | None) -> str | None:
    if difference is None:
        return None
    if difference > 0:
        return "OVER"
    if difference < 0:
        return "SHORT"
    return "EVEN"


def _ensure_not_closed(
    db,
    *,
    tenant_id: str,
    store_id: str,
    business_date: date,
) -> None:
    existing = (
        db.execute(
            select(PosCashDayClose).where(
                PosCashDayClose.tenant_id == tenant_id,
                PosCashDayClose.store_id == store_id,
                PosCashDayClose.business_date == business_date,
            )
        )
        .scalars()
        .first()
    )
    if existing:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "day close already finalized for business_date"},
        )


def _reconciliation_rollup(
    db,
    *,
    tenant_id: str,
    store_id: str,
    business_date: date,
) -> dict[str, Decimal]:
    totals = {key: Decimal("0.00") for key in RECONCILIATION_ACTIONS}
    rows = (
        db.execute(
            select(PosCashMovement.action, func.sum(PosCashMovement.amount), func.count())
            .where(
                PosCashMovement.tenant_id == tenant_id,
                PosCashMovement.store_id == store_id,
                PosCashMovement.business_date == business_date,
            )
            .group_by(PosCashMovement.action)
        )
        .all()
    )
    movement_counts: dict[str, int] = {}
    for action, total_amount, count in rows:
        normalized = _normalize_movement_type(action)
        if normalized in totals:
            totals[normalized] += Decimal(str(total_amount or 0))
        movement_counts[normalized] = movement_counts.get(normalized, 0) + int(count or 0)

    opening_amount = totals["OPENING"]
    cash_in = totals["CASH_IN"]
    cash_out = totals["CASH_OUT"]
    net_cash_movement = cash_in - cash_out
    net_cash_sales = totals["SALE_CASH_IN"]
    cash_refunds = totals["CASH_OUT_REFUND"]
    expected_cash = opening_amount + cash_in - cash_out + net_cash_sales - cash_refunds

    return {
        "opening_amount": opening_amount,
        "cash_in": cash_in,
        "cash_out": cash_out,
        "net_cash_movement": net_cash_movement,
        "net_cash_sales": net_cash_sales,
        "cash_refunds": cash_refunds,
        "expected_cash": expected_cash,
        "movement_counts": movement_counts,
    }


def _open_session_query(db, *, tenant_id: str, store_id: str, cashier_user_id: str, for_update: bool = False):
    day_close_exists = exists(
        select(1).where(
            PosCashDayClose.tenant_id == PosCashSession.tenant_id,
            PosCashDayClose.store_id == PosCashSession.store_id,
            PosCashDayClose.business_date == PosCashSession.business_date,
            PosCashDayClose.status == "CLOSED",
        )
    )
    query = (
        select(PosCashSession)
        .where(
            PosCashSession.tenant_id == tenant_id,
            PosCashSession.store_id == store_id,
            PosCashSession.cashier_user_id == cashier_user_id,
            PosCashSession.status == "OPEN",
            PosCashSession.closed_at.is_(None),
            ~day_close_exists,
        )
        .order_by(PosCashSession.opened_at.desc(), PosCashSession.created_at.desc())
    )
    if for_update:
        query = query.with_for_update()
    return db.execute(query).scalars().first()


def _resolve_active_session(
    db,
    *,
    tenant_id: str,
    store_id: str,
    cashier_user_id: str,
    cash_session_id: str | None,
    for_update: bool = False,
) -> PosCashSession | None:
    if not cash_session_id:
        return _open_session_query(
            db,
            tenant_id=tenant_id,
            store_id=store_id,
            cashier_user_id=cashier_user_id,
            for_update=for_update,
        )
    query = select(PosCashSession).where(
        PosCashSession.id == cash_session_id,
        PosCashSession.tenant_id == tenant_id,
        PosCashSession.store_id == store_id,
        PosCashSession.cashier_user_id == cashier_user_id,
        PosCashSession.status == "OPEN",
        PosCashSession.closed_at.is_(None),
    )
    if for_update:
        query = query.with_for_update()
    return db.execute(query).scalars().first()


def _ensure_positive_amount(value: Decimal | None, field: str) -> Decimal:
    if value is None:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": f"{field} is required"})
    if value <= 0:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": f"{field} must be greater than 0"})
    return value


def _ensure_non_negative_balance(next_balance: Decimal) -> None:
    if next_balance < 0:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "cash_out would result in negative expected balance"},
        )


def _compute_cash_difference(*, counted_cash: Decimal, expected_cash: Decimal) -> Decimal:
    """Canonical cash reconciliation sign convention: counted - expected."""
    return counted_cash - expected_cash


def _cash_cut_summary(cut: PosCashCut) -> PosCashCutSummary:
    return PosCashCutSummary(
        id=_normalize_uuid(cut.id),
        tenant_id=_normalize_uuid(cut.tenant_id),
        store_id=_normalize_uuid(cut.store_id),
        cash_session_id=_normalize_uuid(cut.cash_session_id),
        cut_number=cut.cut_number,
        cut_type=cut.cut_type,
        from_at=cut.from_at,
        to_at=cut.to_at,
        timezone=cut.timezone,
        opening_amount_snapshot=Decimal(str(cut.opening_amount_snapshot)),
        cash_sales_total=Decimal(str(cut.cash_sales_total)),
        card_sales_total=Decimal(str(cut.card_sales_total)),
        transfer_sales_total=Decimal(str(cut.transfer_sales_total)),
        mixed_cash_component_total=Decimal(str(cut.mixed_cash_component_total)),
        mixed_card_component_total=Decimal(str(cut.mixed_card_component_total)),
        mixed_transfer_component_total=Decimal(str(cut.mixed_transfer_component_total)),
        cash_in_total=Decimal(str(cut.cash_in_total)),
        cash_out_total=Decimal(str(cut.cash_out_total)),
        cash_refunds_total=Decimal(str(cut.cash_refunds_total)),
        expected_cash=Decimal(str(cut.expected_cash)),
        counted_cash=Decimal(str(cut.counted_cash)) if cut.counted_cash is not None else None,
        difference=Decimal(str(cut.difference)) if cut.difference is not None else None,
        deposit_removed_amount=Decimal(str(cut.deposit_removed_amount)) if cut.deposit_removed_amount is not None else None,
        deposit_cash_movement_id=_normalize_uuid(cut.deposit_cash_movement_id) if cut.deposit_cash_movement_id else None,
        notes=cut.notes,
        status=cut.status,
        created_by_user_id=_normalize_uuid(cut.created_by_user_id),
        created_at=cut.created_at,
        completed_at=cut.completed_at,
    )


def _resolve_cut_window(db, *, session: PosCashSession, use_last_cut_window: bool, from_at: datetime | None, to_at: datetime | None) -> tuple[datetime, datetime]:
    to_value = to_at or datetime.utcnow()
    if from_at:
        return from_at, to_value
    if use_last_cut_window:
        last_cut = (
            db.execute(
                select(PosCashCut)
                .where(PosCashCut.cash_session_id == session.id)
                .order_by(PosCashCut.cut_number.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )
        if last_cut:
            return last_cut.to_at, to_value
    return session.opened_at, to_value


def _calculate_cut_quote(
    db,
    *,
    tenant_id: str,
    store_id: str,
    session: PosCashSession,
    cut_type: str,
    from_at: datetime,
    to_at: datetime,
    timezone: str,
    counted_cash: Decimal | None = None,
    deposit_removed_amount: Decimal | None = None,
    notes: str | None = None,
    existing_cut_id: str | None = None,
) -> PosCashCutSummary:
    if to_at <= from_at:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "to_at must be greater than from_at"})

    prior_rows = db.execute(
        select(PosCashMovement.action, func.sum(PosCashMovement.amount))
        .where(
            PosCashMovement.tenant_id == tenant_id,
            PosCashMovement.store_id == store_id,
            PosCashMovement.cash_session_id == session.id,
            PosCashMovement.occurred_at >= session.opened_at,
            PosCashMovement.occurred_at < from_at,
            PosCashMovement.action.in_(["CASH_IN", "CASH_OUT", "SALE", "CASH_OUT_REFUND"]),
        )
        .group_by(PosCashMovement.action)
    ).all()
    prior_totals = {action: Decimal(str(total or 0)) for action, total in prior_rows}
    opening_snapshot = (
        Decimal(str(session.opening_amount or 0))
        + prior_totals.get("CASH_IN", Decimal("0.00"))
        - prior_totals.get("CASH_OUT", Decimal("0.00"))
        + prior_totals.get("SALE", Decimal("0.00"))
        - prior_totals.get("CASH_OUT_REFUND", Decimal("0.00"))
    )

    payment_rows = db.execute(
        select(
            PosSale.id,
            func.count(PosPayment.id),
            func.sum(case((PosPayment.method == "CASH", PosPayment.amount), else_=0.0)),
            func.sum(case((PosPayment.method == "CARD", PosPayment.amount), else_=0.0)),
            func.sum(case((PosPayment.method == "TRANSFER", PosPayment.amount), else_=0.0)),
        )
        .select_from(PosSale)
        .join(PosPayment, PosPayment.sale_id == PosSale.id)
        .where(
            PosSale.tenant_id == tenant_id,
            PosSale.store_id == store_id,
            PosSale.status == "PAID",
            PosSale.checked_out_at >= from_at,
            PosSale.checked_out_at <= to_at,
        )
        .group_by(PosSale.id)
    ).all()
    cash_sales = card_sales = transfer_sales = Decimal("0.00")
    mixed_cash = mixed_card = mixed_transfer = Decimal("0.00")
    for _sale_id, payment_count, cash_amount, card_amount, transfer_amount in payment_rows:
        sale_cash = Decimal(str(cash_amount or 0))
        sale_card = Decimal(str(card_amount or 0))
        sale_transfer = Decimal(str(transfer_amount or 0))
        cash_sales += sale_cash
        card_sales += sale_card
        transfer_sales += sale_transfer
        if int(payment_count or 0) > 1:
            mixed_cash += sale_cash
            mixed_card += sale_card
            mixed_transfer += sale_transfer

    movement_rows = db.execute(
        select(PosCashMovement.action, func.sum(PosCashMovement.amount))
        .where(
            PosCashMovement.tenant_id == tenant_id,
            PosCashMovement.store_id == store_id,
            PosCashMovement.cash_session_id == session.id,
            PosCashMovement.occurred_at >= from_at,
            PosCashMovement.occurred_at <= to_at,
            PosCashMovement.action.in_(["CASH_IN", "CASH_OUT", "CASH_OUT_REFUND"]),
        )
        .group_by(PosCashMovement.action)
    ).all()
    movement_totals = {action: Decimal(str(total or 0)) for action, total in movement_rows}
    cash_in_total = movement_totals.get("CASH_IN", Decimal("0.00"))
    cash_out_total = movement_totals.get("CASH_OUT", Decimal("0.00"))
    cash_refunds_total = movement_totals.get("CASH_OUT_REFUND", Decimal("0.00"))
    expected_cash = opening_snapshot + cash_sales + cash_in_total - cash_out_total - cash_refunds_total
    difference = (counted_cash - expected_cash) if counted_cash is not None else None

    cut_number = (
        db.execute(select(func.max(PosCashCut.cut_number)).where(PosCashCut.cash_session_id == session.id)).scalar_one()
        or 0
    ) + 1
    quote_id = existing_cut_id or "00000000-0000-0000-0000-000000000000"
    return PosCashCutSummary(
        id=quote_id,
        tenant_id=tenant_id,
        store_id=store_id,
        cash_session_id=_normalize_uuid(session.id),
        cut_number=cut_number,
        cut_type=cut_type,
        from_at=from_at,
        to_at=to_at,
        timezone=timezone,
        opening_amount_snapshot=opening_snapshot,
        cash_sales_total=cash_sales,
        card_sales_total=card_sales,
        transfer_sales_total=transfer_sales,
        mixed_cash_component_total=mixed_cash,
        mixed_card_component_total=mixed_card,
        mixed_transfer_component_total=mixed_transfer,
        cash_in_total=cash_in_total,
        cash_out_total=cash_out_total,
        cash_refunds_total=cash_refunds_total,
        expected_cash=expected_cash,
        counted_cash=counted_cash,
        difference=difference,
        deposit_removed_amount=deposit_removed_amount,
        deposit_cash_movement_id=None,
        notes=notes,
        status="OPEN",
        created_by_user_id=_normalize_uuid(session.cashier_user_id),
        created_at=datetime.utcnow(),
        completed_at=None,
    )

@router.get("/aris3/pos/cash/session/current", response_model=PosCashSessionCurrentResponse, responses=POS_STANDARD_ERROR_RESPONSES, summary="Get current open cash session", description="Returns the currently OPEN cash session for the cashier/store context. `closed_at` is null while session is open.", openapi_extra={
    "responses": {
        "200": {"content": {"application/json": {"example": {"session": {"id": "00000000-0000-0000-0000-000000000211", "tenant_id": "00000000-0000-0000-0000-000000000010", "store_id": "00000000-0000-0000-0000-000000000001", "cashier_user_id": "00000000-0000-0000-0000-000000000020", "status": "OPEN", "business_date": "2026-01-15", "timezone": "America/Mexico_City", "opening_amount": "100.00", "expected_cash": "150.00", "counted_cash": None, "difference": None, "opened_at": "2026-01-15T08:00:00Z", "closed_at": None, "created_at": "2026-01-15T08:00:00Z"}}}}},
        "401": {"content": {"application/json": {"example": CASH_ERROR_EXAMPLES["401"]}}},
        "403": {"content": {"application/json": {"example": CASH_ERROR_EXAMPLES["403"]}}},
        "404": {"content": {"application/json": {"example": CASH_ERROR_EXAMPLES["404_session"]}}},
    }
})
def get_current_session(
    request: Request,
    store_id: str | None = None,
    cashier_user_id: str | None = None,
    tenant_id: Annotated[str | None, Query(description="Tenant scope. Required for superadmin roles; ignored for tenant-scoped roles.")] = None,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    _permission=Depends(require_permission("POS_CASH_VIEW")),
    db=Depends(get_db),
):
    scoped_tenant_id = _resolve_tenant_id(token_data, tenant_id)
    store_id = _resolve_store_id(token_data, store_id)
    enforce_store_scope(token_data, store_id, db, allow_superadmin=True)
    if not cashier_user_id:
        cashier_user_id = str(current_user.id)
    logger.info(
        "pos.cash_session.current.resolve.start tenant_id=%s store_id=%s cashier_user_id=%s trace_id=%s register_id=%s terminal_id=%s",
        scoped_tenant_id,
        store_id,
        cashier_user_id,
        getattr(request.state, "trace_id", None) if hasattr(request, "state") else None,
        None,
        None,
    )
    session = _open_session_query(
        db,
        tenant_id=scoped_tenant_id,
        store_id=store_id,
        cashier_user_id=cashier_user_id,
        for_update=False,
    )
    if session is None:
        logger.warning(
            "pos.cash_session.current.resolve.missing tenant_id=%s store_id=%s cashier_user_id=%s trace_id=%s register_id=%s terminal_id=%s",
            scoped_tenant_id,
            store_id,
            cashier_user_id,
            getattr(request.state, "trace_id", None) if hasattr(request, "state") else None,
            None,
            None,
        )
        raise AppError(
            ErrorCatalog.RESOURCE_NOT_FOUND,
            details={"message": "open cash session not found"},
        )
    logger.info(
        "pos.cash_session.current.resolve.ok tenant_id=%s store_id=%s cashier_user_id=%s cash_session_id=%s trace_id=%s register_id=%s terminal_id=%s",
        scoped_tenant_id,
        store_id,
        cashier_user_id,
        str(session.id),
        getattr(request.state, "trace_id", None) if hasattr(request, "state") else None,
        None,
        None,
    )
    return PosCashSessionCurrentResponse(session=_session_summary(session))


@router.post("/aris3/pos/cash/session/actions", response_model=PosCashSessionSummary, responses=POS_STANDARD_ERROR_RESPONSES, summary="Execute cash session action", description="Action request is discriminated by `action` (`OPEN`, `CASH_IN`, `CASH_OUT`, `CLOSE`) with action-specific required fields.", openapi_extra={
    "parameters": [_IDEMPOTENCY_REQUIRED_HEADER_PARAMETER],
    "responses": {
        "200": {"content": {"application/json": {"example": {"id": "00000000-0000-0000-0000-000000000212", "tenant_id": "00000000-0000-0000-0000-000000000010", "store_id": "00000000-0000-0000-0000-000000000001", "cashier_user_id": "00000000-0000-0000-0000-000000000020", "status": "OPEN", "business_date": "2026-01-15", "timezone": "America/Mexico_City", "opening_amount": "150.00", "expected_cash": "150.00", "counted_cash": None, "difference": None, "opened_at": "2026-01-15T08:00:00Z", "closed_at": None, "created_at": "2026-01-15T08:00:00Z"}}}},
        "401": {"content": {"application/json": {"example": CASH_ERROR_EXAMPLES["401"]}}},
        "403": {"content": {"application/json": {"example": CASH_ERROR_EXAMPLES["403"]}}},
        "404": {"content": {"application/json": {"example": CASH_ERROR_EXAMPLES["404_session"]}}},
        "409": {"content": {"application/json": {"example": CASH_ERROR_EXAMPLES["409"]}}},
        "422": {"content": {"application/json": {"example": {"code": "VALIDATION_ERROR", "message": "Validation error", "details": {"errors": [{"field": "action=OPEN.business_date", "message": "business_date is required", "type": "value_error"}]}, "trace_id": "trace-cash-session-action-422"}}}},
    }
})
def cash_session_action(
    request: Request,
    payload: PosCashSessionActionRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    _permission=Depends(require_permission("POS_CASH_MANAGE")),
    db=Depends(get_db),
):
    _require_transaction_id(payload.transaction_id)
    scoped_tenant_id = _resolve_tenant_id(token_data, payload.tenant_id)
    enforce_tenant_scope(token_data, scoped_tenant_id, allow_superadmin=True)
    resolved_store_id = _resolve_store_id(token_data, payload.store_id)
    store = enforce_store_scope(token_data, resolved_store_id, db, allow_superadmin=True)

    idempotency_key = extract_idempotency_key(request.headers, required=True)
    request_hash = IdempotencyService.fingerprint(payload.model_dump(mode="json"))
    idempotency_service = IdempotencyService(db)
    context, replay = idempotency_service.start(
        tenant_id=scoped_tenant_id,
        endpoint=str(request.url.path),
        method=request.method,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )
    if replay:
        return JSONResponse(
            status_code=replay.status_code,
            content=replay.response_body,
            headers={"X-Idempotency-Result": ErrorCatalog.IDEMPOTENCY_REPLAY.code},
        )
    request.state.idempotency = context

    now = datetime.utcnow()
    cashier_user_id = str(current_user.id)

    if payload.action == "OPEN":
        opening_amount = _ensure_positive_amount(payload.opening_amount, "opening_amount")
        if not payload.business_date or not payload.timezone:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "business_date and timezone are required"},
            )
        _ensure_not_closed(
            db,
            tenant_id=scoped_tenant_id,
            store_id=resolved_store_id,
            business_date=payload.business_date,
        )
        existing = _open_session_query(
            db,
            tenant_id=scoped_tenant_id,
            store_id=resolved_store_id,
            cashier_user_id=cashier_user_id,
            for_update=True,
        )
        if existing:
            raise AppError(
                ErrorCatalog.BUSINESS_CONFLICT,
                details={"message": "open cash session already exists"},
            )

        session = PosCashSession(
            tenant_id=scoped_tenant_id,
            store_id=resolved_store_id,
            cashier_user_id=current_user.id,
            status="OPEN",
            business_date=payload.business_date,
            timezone=payload.timezone,
            opening_amount=float(opening_amount),
            expected_cash=float(opening_amount),
            opened_at=now,
            created_at=now,
        )
        db.add(session)
        db.flush()
        logger.info(
            "pos.cash_session.open tenant_id=%s store_id=%s cashier_user_id=%s cash_session_id=%s business_date=%s trace_id=%s register_id=%s terminal_id=%s",
            scoped_tenant_id,
            resolved_store_id,
            cashier_user_id,
            str(session.id),
            str(payload.business_date),
            getattr(request.state, "trace_id", None),
            None,
            None,
        )
        db.add(
            PosCashMovement(
                tenant_id=scoped_tenant_id,
                store_id=resolved_store_id,
                cash_session_id=session.id,
                cashier_user_id=current_user.id,
                actor_user_id=current_user.id,
                business_date=payload.business_date,
                timezone=payload.timezone,
                sale_id=None,
                action="OPEN",
                amount=float(opening_amount),
                expected_balance_before=0.0,
                expected_balance_after=float(opening_amount),
                transaction_id=payload.transaction_id,
                reason=payload.reason,
                trace_id=getattr(request.state, "trace_id", None),
                occurred_at=now,
                created_at=now,
            )
        )
        db.commit()
        response = _session_summary(session)
        context.record_success(status_code=200, response_body=response.model_dump(mode="json"))
        AuditService(db).record_event(
            AuditEventPayload(
                tenant_id=scoped_tenant_id,
                user_id=cashier_user_id,
                store_id=str(store.id),
                trace_id=getattr(request.state, "trace_id", None),
                actor=str(current_user.username),
                action="pos_cash_session.open",
                entity_type="pos_cash_session",
                entity_id=str(session.id),
                before=None,
                after={
                    "status": session.status,
                    "opening_amount": str(opening_amount),
                    "expected_cash": str(opening_amount),
                    "business_date": str(payload.business_date),
                    "timezone": payload.timezone,
                },
                metadata={"transaction_id": payload.transaction_id, "reason": payload.reason},
                result="success",
            )
        )
        return response

    session = _open_session_query(
        db,
        tenant_id=scoped_tenant_id,
        store_id=resolved_store_id,
        cashier_user_id=cashier_user_id,
        for_update=True,
    )
    if not session:
        raise AppError(
            ErrorCatalog.BUSINESS_CONFLICT,
            details={"message": "open cash session required"},
        )
    _ensure_not_closed(
        db,
        tenant_id=scoped_tenant_id,
        store_id=resolved_store_id,
        business_date=session.business_date,
    )
    if session.status != "OPEN":
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "cash session is not open"},
        )

    expected_before = Decimal(str(session.expected_cash or 0))
    counted_before = Decimal(str(session.counted_cash)) if session.counted_cash is not None else None
    difference_before = Decimal(str(session.difference)) if session.difference is not None else None

    if payload.action == "CASH_IN":
        amount = _ensure_positive_amount(payload.amount, "amount")
        expected_after = expected_before + amount
        session.expected_cash = float(expected_after)
        movement_action = "CASH_IN"
        movement_amount = amount
        counted_cash = None
        difference = None
        status_before = session.status
        status_after = session.status
    elif payload.action == "CASH_OUT":
        amount = _ensure_positive_amount(payload.amount, "amount")
        expected_after = expected_before - amount
        _ensure_non_negative_balance(expected_after)
        session.expected_cash = float(expected_after)
        movement_action = "CASH_OUT"
        movement_amount = amount
        counted_cash = None
        difference = None
        status_before = session.status
        status_after = session.status
    elif payload.action == "CLOSE":
        if payload.counted_cash is None:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "counted_cash is required"},
            )
        counted_cash = Decimal(str(payload.counted_cash))
        expected_after = expected_before
        difference = counted_cash - expected_before
        session.counted_cash = float(counted_cash)
        session.difference = float(difference)
        session.status = "CLOSED"
        session.closed_at = now
        movement_action = "CLOSE"
        movement_amount = Decimal("0.00")
        status_before = "OPEN"
        status_after = "CLOSED"
        logger.info(
            "pos.cash_session.close tenant_id=%s store_id=%s cashier_user_id=%s cash_session_id=%s business_date=%s trace_id=%s register_id=%s terminal_id=%s",
            scoped_tenant_id,
            resolved_store_id,
            cashier_user_id,
            str(session.id),
            str(session.business_date),
            getattr(request.state, "trace_id", None),
            None,
            None,
        )
    else:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "unsupported action"})

    db.add(
        PosCashMovement(
            tenant_id=scoped_tenant_id,
            store_id=resolved_store_id,
            cash_session_id=session.id,
            cashier_user_id=session.cashier_user_id,
            actor_user_id=current_user.id,
            business_date=session.business_date,
            timezone=session.timezone,
            sale_id=None,
            action=movement_action,
            amount=float(movement_amount),
            expected_balance_before=float(expected_before),
            expected_balance_after=float(expected_after),
            transaction_id=payload.transaction_id,
            reason=payload.reason,
            trace_id=getattr(request.state, "trace_id", None),
            occurred_at=now,
            created_at=now,
        )
    )
    db.commit()
    response = _session_summary(session)
    context.record_success(status_code=200, response_body=response.model_dump(mode="json"))
    AuditService(db).record_event(
        AuditEventPayload(
            tenant_id=scoped_tenant_id,
            user_id=cashier_user_id,
            store_id=str(store.id),
            trace_id=getattr(request.state, "trace_id", None),
            actor=str(current_user.username),
            action=f"pos_cash_session.{movement_action.lower()}",
            entity_type="pos_cash_session",
            entity_id=str(session.id),
            before={
                "status": status_before,
                "expected_cash": str(expected_before),
                "opening_amount": str(session.opening_amount),
                "counted_cash": str(counted_before) if counted_before is not None else None,
                "difference": str(difference_before) if difference_before is not None else None,
            },
            after={
                "status": status_after,
                "expected_cash": str(expected_after),
                "opening_amount": str(session.opening_amount),
                "counted_cash": str(counted_cash) if counted_cash is not None else None,
                "difference": str(difference) if difference is not None else None,
            },
            metadata={"transaction_id": payload.transaction_id, "reason": payload.reason},
            result="success",
        )
    )
    return response


@router.get("/aris3/pos/cash/movements", response_model=PosCashMovementListResponse, responses=POS_LIST_ERROR_RESPONSES)
def list_cash_movements(
    store_id: str | None = None,
    cashier_user_id: str | None = None,
    movement_type: str | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    tenant_id: Annotated[str | None, Query(description="Tenant scope. Required for superadmin roles; ignored for tenant-scoped roles.")] = None,
    token_data=Depends(get_current_token_data),
    _user=Depends(require_active_user),
    _permission=Depends(require_permission("POS_CASH_VIEW")),
    db=Depends(get_db),
):
    scoped_tenant_id = _resolve_tenant_id(token_data, tenant_id)
    store_id = _resolve_store_id(token_data, store_id)
    enforce_store_scope(token_data, store_id, db, allow_superadmin=True)

    offset = (page - 1) * page_size

    query = select(PosCashMovement).where(PosCashMovement.tenant_id == scoped_tenant_id)
    count_query = select(func.count()).select_from(PosCashMovement).where(PosCashMovement.tenant_id == scoped_tenant_id)
    if store_id:
        query = query.where(PosCashMovement.store_id == store_id)
        count_query = count_query.where(PosCashMovement.store_id == store_id)
    if cashier_user_id:
        query = query.where(PosCashMovement.cashier_user_id == cashier_user_id)
        count_query = count_query.where(PosCashMovement.cashier_user_id == cashier_user_id)
    if movement_type:
        query = query.where(PosCashMovement.action == movement_type)
        count_query = count_query.where(PosCashMovement.action == movement_type)
    if occurred_from:
        query = query.where(PosCashMovement.occurred_at >= occurred_from)
        count_query = count_query.where(PosCashMovement.occurred_at >= occurred_from)
    if occurred_to:
        query = query.where(PosCashMovement.occurred_at <= occurred_to)
        count_query = count_query.where(PosCashMovement.occurred_at <= occurred_to)

    total = db.execute(count_query).scalar_one()
    rows = db.execute(query.order_by(PosCashMovement.created_at.desc()).limit(page_size).offset(offset)).scalars().all()
    return PosCashMovementListResponse(page=page, page_size=page_size, rows=[_movement_response(row) for row in rows], total=total)


@router.post("/aris3/pos/cash/cuts/quote", response_model=PosCashCutQuoteResponse, responses=POS_STANDARD_ERROR_RESPONSES)
def quote_cash_cut(
    payload: PosCashCutQuoteRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    _permission=Depends(require_permission("POS_CASH_VIEW")),
    db=Depends(get_db),
):
    scoped_tenant_id = _resolve_tenant_id(token_data, payload.tenant_id)
    enforce_tenant_scope(token_data, scoped_tenant_id, allow_superadmin=True)
    resolved_store_id = _resolve_store_id(token_data, payload.store_id)
    enforce_store_scope(token_data, resolved_store_id, db, allow_superadmin=True)
    session = _resolve_active_session(
        db,
        tenant_id=scoped_tenant_id,
        store_id=resolved_store_id,
        cashier_user_id=str(current_user.id),
        cash_session_id=payload.cash_session_id,
        for_update=False,
    )
    if session is None:
        raise AppError(ErrorCatalog.BUSINESS_CONFLICT, details={"message": "open cash session required"})
    _ensure_not_closed(db, tenant_id=scoped_tenant_id, store_id=resolved_store_id, business_date=session.business_date)
    from_at, to_at = _resolve_cut_window(
        db,
        session=session,
        use_last_cut_window=payload.use_last_cut_window,
        from_at=payload.from_at,
        to_at=payload.to_at,
    )
    quote = _calculate_cut_quote(
        db,
        tenant_id=scoped_tenant_id,
        store_id=resolved_store_id,
        session=session,
        cut_type=payload.cut_type,
        from_at=from_at,
        to_at=to_at,
        timezone=payload.timezone or session.timezone,
    )
    quote.created_by_user_id = _normalize_uuid(current_user.id)
    return PosCashCutQuoteResponse(quote=quote)


@router.post("/aris3/pos/cash/cuts", response_model=PosCashCutDetailResponse, responses=POS_STANDARD_ERROR_RESPONSES)
def create_cash_cut(
    request: Request,
    payload: PosCashCutCreateRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    _permission=Depends(require_permission("POS_CASH_MANAGE")),
    db=Depends(get_db),
):
    _require_transaction_id(payload.transaction_id)
    scoped_tenant_id = _resolve_tenant_id(token_data, payload.tenant_id)
    enforce_tenant_scope(token_data, scoped_tenant_id, allow_superadmin=True)
    resolved_store_id = _resolve_store_id(token_data, payload.store_id)
    enforce_store_scope(token_data, resolved_store_id, db, allow_superadmin=True)
    session = _resolve_active_session(
        db,
        tenant_id=scoped_tenant_id,
        store_id=resolved_store_id,
        cashier_user_id=str(current_user.id),
        cash_session_id=payload.cash_session_id,
        for_update=True,
    )
    if session is None:
        raise AppError(ErrorCatalog.BUSINESS_CONFLICT, details={"message": "open cash session required"})
    _ensure_not_closed(db, tenant_id=scoped_tenant_id, store_id=resolved_store_id, business_date=session.business_date)
    from_at, to_at = _resolve_cut_window(
        db,
        session=session,
        use_last_cut_window=payload.use_last_cut_window,
        from_at=payload.from_at,
        to_at=payload.to_at,
    )
    counted_cash = Decimal(str(payload.counted_cash)) if payload.counted_cash is not None else None
    deposit_removed = Decimal(str(payload.deposit_removed_amount)) if payload.deposit_removed_amount is not None else None
    quote = _calculate_cut_quote(
        db,
        tenant_id=scoped_tenant_id,
        store_id=resolved_store_id,
        session=session,
        cut_type=payload.cut_type,
        from_at=from_at,
        to_at=to_at,
        timezone=payload.timezone or session.timezone,
        counted_cash=counted_cash,
        deposit_removed_amount=deposit_removed,
        notes=payload.notes,
    )
    now = datetime.utcnow()
    cut = PosCashCut(
        tenant_id=scoped_tenant_id,
        store_id=resolved_store_id,
        cash_session_id=session.id,
        cut_number=quote.cut_number,
        cut_type=quote.cut_type,
        from_at=quote.from_at,
        to_at=quote.to_at,
        timezone=quote.timezone,
        opening_amount_snapshot=float(quote.opening_amount_snapshot),
        cash_sales_total=float(quote.cash_sales_total),
        card_sales_total=float(quote.card_sales_total),
        transfer_sales_total=float(quote.transfer_sales_total),
        mixed_cash_component_total=float(quote.mixed_cash_component_total),
        mixed_card_component_total=float(quote.mixed_card_component_total),
        mixed_transfer_component_total=float(quote.mixed_transfer_component_total),
        cash_in_total=float(quote.cash_in_total),
        cash_out_total=float(quote.cash_out_total),
        cash_refunds_total=float(quote.cash_refunds_total),
        expected_cash=float(quote.expected_cash),
        counted_cash=float(quote.counted_cash) if quote.counted_cash is not None else None,
        difference=float(quote.difference) if quote.difference is not None else None,
        deposit_removed_amount=float(deposit_removed) if deposit_removed is not None else None,
        notes=payload.notes,
        status="COMPLETED" if counted_cash is not None else "OPEN",
        created_by_user_id=current_user.id,
        created_at=now,
        completed_at=now if counted_cash is not None else None,
    )
    db.add(cut)
    if payload.auto_apply_cash_out and deposit_removed and deposit_removed > 0:
        expected_before = Decimal(str(session.expected_cash or 0))
        expected_after = expected_before - deposit_removed
        _ensure_non_negative_balance(expected_after)
        session.expected_cash = float(expected_after)
        movement = PosCashMovement(
            tenant_id=scoped_tenant_id,
            store_id=resolved_store_id,
            cash_session_id=session.id,
            cashier_user_id=session.cashier_user_id,
            actor_user_id=current_user.id,
            business_date=session.business_date,
            timezone=session.timezone,
            sale_id=None,
            action="CASH_OUT",
            amount=float(deposit_removed),
            expected_balance_before=float(expected_before),
            expected_balance_after=float(expected_after),
            transaction_id=f"{payload.transaction_id}-cut-deposit",
            reason=payload.notes or "bank deposit",
            trace_id=getattr(request.state, "trace_id", None),
            occurred_at=now,
            created_at=now,
        )
        db.add(movement)
        db.flush()
        cut.deposit_cash_movement_id = movement.id
    db.commit()
    return PosCashCutDetailResponse(cut=_cash_cut_summary(cut))


@router.get("/aris3/pos/cash/cuts", response_model=PosCashCutListResponse, responses=POS_LIST_ERROR_RESPONSES)
def list_cash_cuts(
    store_id: str | None = None,
    cash_session_id: str | None = None,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    tenant_id: Annotated[str | None, Query(description="Tenant scope. Required for superadmin roles; ignored for tenant-scoped roles.")] = None,
    token_data=Depends(get_current_token_data),
    _user=Depends(require_active_user),
    _permission=Depends(require_permission("POS_CASH_VIEW")),
    db=Depends(get_db),
):
    scoped_tenant_id = _resolve_tenant_id(token_data, tenant_id)
    store_id = _resolve_store_id(token_data, store_id)
    enforce_store_scope(token_data, store_id, db, allow_superadmin=True)
    offset = (page - 1) * page_size
    query = select(PosCashCut).where(PosCashCut.tenant_id == scoped_tenant_id, PosCashCut.store_id == store_id)
    count_query = select(func.count()).select_from(PosCashCut).where(PosCashCut.tenant_id == scoped_tenant_id, PosCashCut.store_id == store_id)
    if cash_session_id:
        query = query.where(PosCashCut.cash_session_id == cash_session_id)
        count_query = count_query.where(PosCashCut.cash_session_id == cash_session_id)
    if status:
        query = query.where(PosCashCut.status == status)
        count_query = count_query.where(PosCashCut.status == status)
    total = db.execute(count_query).scalar_one()
    rows = db.execute(query.order_by(PosCashCut.created_at.desc()).limit(page_size).offset(offset)).scalars().all()
    return PosCashCutListResponse(page=page, page_size=page_size, total=total, rows=[_cash_cut_summary(row) for row in rows])


@router.get("/aris3/pos/cash/cuts/{cut_id}", response_model=PosCashCutDetailResponse, responses=POS_STANDARD_ERROR_RESPONSES)
def get_cash_cut(
    cut_id: str,
    store_id: str | None = None,
    tenant_id: Annotated[str | None, Query(description="Tenant scope. Required for superadmin roles; ignored for tenant-scoped roles.")] = None,
    token_data=Depends(get_current_token_data),
    _user=Depends(require_active_user),
    _permission=Depends(require_permission("POS_CASH_VIEW")),
    db=Depends(get_db),
):
    scoped_tenant_id = _resolve_tenant_id(token_data, tenant_id)
    store_id = _resolve_store_id(token_data, store_id)
    enforce_store_scope(token_data, store_id, db, allow_superadmin=True)
    cut = db.execute(select(PosCashCut).where(PosCashCut.id == cut_id, PosCashCut.tenant_id == scoped_tenant_id, PosCashCut.store_id == store_id)).scalars().first()
    if cut is None:
        raise AppError(ErrorCatalog.RESOURCE_NOT_FOUND, details={"message": "cash cut not found"})
    return PosCashCutDetailResponse(cut=_cash_cut_summary(cut))


@router.post("/aris3/pos/cash/cuts/{cut_id}/actions", response_model=PosCashCutDetailResponse, responses=POS_STANDARD_ERROR_RESPONSES)
def cash_cut_action(
    request: Request,
    cut_id: str,
    payload: PosCashCutActionRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    _permission=Depends(require_permission("POS_CASH_MANAGE")),
    db=Depends(get_db),
):
    _require_transaction_id(payload.transaction_id)
    scoped_tenant_id = _resolve_tenant_id(token_data, payload.tenant_id)
    store_id = _resolve_store_id(token_data, payload.store_id)
    enforce_store_scope(token_data, store_id, db, allow_superadmin=True)
    cut = db.execute(select(PosCashCut).where(PosCashCut.id == cut_id, PosCashCut.tenant_id == scoped_tenant_id, PosCashCut.store_id == store_id)).scalars().first()
    if cut is None:
        raise AppError(ErrorCatalog.RESOURCE_NOT_FOUND, details={"message": "cash cut not found"})
    now = datetime.utcnow()
    if payload.action == "VOID":
        cut.status = "VOID"
    elif payload.action == "COMPLETE":
        if payload.counted_cash is None:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "counted_cash is required"},
            )
        counted_cash = Decimal(str(payload.counted_cash))
        expected_cash = Decimal(str(cut.expected_cash or 0))
        difference = _compute_cash_difference(counted_cash=counted_cash, expected_cash=expected_cash)
        cut.status = "COMPLETED"
        cut.counted_cash = float(counted_cash)
        cut.difference = float(difference)
        cut.notes = payload.notes
        cut.completed_at = now
    elif payload.action == "PRINT_MARK":
        cut.notes = f"{cut.notes or ''}\nprint_mark:{now.isoformat()}".strip()
    elif payload.action == "APPLY_CASH_OUT":
        amount = _ensure_positive_amount(payload.amount, "amount")
        session = db.execute(select(PosCashSession).where(PosCashSession.id == cut.cash_session_id).with_for_update()).scalars().first()
        if session is None or session.status != "OPEN":
            raise AppError(ErrorCatalog.BUSINESS_CONFLICT, details={"message": "open cash session required"})
        expected_before = Decimal(str(session.expected_cash or 0))
        expected_after = expected_before - amount
        _ensure_non_negative_balance(expected_after)
        session.expected_cash = float(expected_after)
        movement = PosCashMovement(
            tenant_id=scoped_tenant_id,
            store_id=store_id,
            cash_session_id=session.id,
            cashier_user_id=session.cashier_user_id,
            actor_user_id=current_user.id,
            business_date=session.business_date,
            timezone=session.timezone,
            sale_id=None,
            action="CASH_OUT",
            amount=float(amount),
            expected_balance_before=float(expected_before),
            expected_balance_after=float(expected_after),
            transaction_id=f"{payload.transaction_id}-cut-action",
            reason=payload.reason or "cut cash out",
            trace_id=getattr(request.state, "trace_id", None),
            occurred_at=now,
            created_at=now,
        )
        db.add(movement)
        db.flush()
        cut.deposit_removed_amount = float(amount)
        cut.deposit_cash_movement_id = movement.id
    db.flush()
    db.commit()
    db.refresh(cut)
    return PosCashCutDetailResponse(cut=_cash_cut_summary(cut))


@router.post("/aris3/pos/cash/day-close/actions", response_model=PosCashDayCloseResponse, responses=POS_STANDARD_ERROR_RESPONSES, summary="Execute cash day close", description="Performs day-close for the requested business date and timezone.", openapi_extra={
    "parameters": [_IDEMPOTENCY_REQUIRED_HEADER_PARAMETER],
    "responses": {
        "422": {"content": {"application/json": {"example": {"code": "VALIDATION_ERROR", "message": "Validation error", "details": {"errors": [{"field": "reason", "message": "reason is required for force day close", "type": "value_error"}]}, "trace_id": "trace-day-close-422"}}}}
    }
})
def close_day(
    request: Request,
    payload: PosCashDayCloseActionRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    _permission=Depends(require_permission("POS_CASH_DAY_CLOSE")),
    db=Depends(get_db),
):
    _require_transaction_id(payload.transaction_id)
    scoped_tenant_id = _resolve_tenant_id(token_data, payload.tenant_id)
    enforce_tenant_scope(token_data, scoped_tenant_id, allow_superadmin=True)
    resolved_store_id = _resolve_store_id(token_data, payload.store_id)
    store = enforce_store_scope(token_data, resolved_store_id, db, allow_superadmin=True)

    idempotency_key = extract_idempotency_key(request.headers, required=True)
    request_hash = IdempotencyService.fingerprint(payload.model_dump(mode="json"))
    idempotency_service = IdempotencyService(db)
    context, replay = idempotency_service.start(
        tenant_id=scoped_tenant_id,
        endpoint=str(request.url.path),
        method=request.method,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )
    if replay:
        return JSONResponse(
            status_code=replay.status_code,
            content=replay.response_body,
            headers={"X-Idempotency-Result": ErrorCatalog.IDEMPOTENCY_REPLAY.code},
        )
    request.state.idempotency = context

    existing = (
        db.execute(
            select(PosCashDayClose).where(
                PosCashDayClose.tenant_id == scoped_tenant_id,
                PosCashDayClose.store_id == resolved_store_id,
                PosCashDayClose.business_date == payload.business_date,
            )
        )
        .scalars()
        .first()
    )
    if existing:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "day close already exists"},
        )

    open_sessions = (
        db.execute(
            select(PosCashSession).where(
                PosCashSession.tenant_id == scoped_tenant_id,
                PosCashSession.store_id == resolved_store_id,
                PosCashSession.business_date == payload.business_date,
                PosCashSession.status == "OPEN",
            )
            .with_for_update()
        )
        .scalars()
        .all()
    )
    force_close = bool(payload.force_if_open_sessions)
    if open_sessions and not force_close:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={
                "message": "open cash sessions exist for business_date",
                "open_sessions": [str(session.id) for session in open_sessions],
            },
        )
    if open_sessions and force_close:
        role = (token_data.role or "").upper()
        if role not in {"MANAGER", "ADMIN", "SUPERADMIN", "PLATFORM_ADMIN"}:
            raise AppError(ErrorCatalog.PERMISSION_DENIED)
        if not payload.reason:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "reason is required for force day close"},
            )
        for session in open_sessions:
            session.status = "CLOSED"
            session.closed_at = datetime.utcnow()

    rollup = _reconciliation_rollup(
        db,
        tenant_id=scoped_tenant_id,
        store_id=resolved_store_id,
        business_date=payload.business_date,
    )
    counted_cash = Decimal(str(payload.counted_cash)) if payload.counted_cash is not None else None
    difference_amount = counted_cash - rollup["expected_cash"] if counted_cash is not None else None
    difference_type = _difference_type(difference_amount)

    now = datetime.utcnow()
    close_record = PosCashDayClose(
        tenant_id=scoped_tenant_id,
        store_id=resolved_store_id,
        business_date=payload.business_date,
        timezone=payload.timezone,
        status="CLOSED",
        force_close=force_close,
        reason=payload.reason,
        expected_cash=float(rollup["expected_cash"]),
        counted_cash=float(counted_cash) if counted_cash is not None else None,
        difference_amount=float(difference_amount) if difference_amount is not None else None,
        difference_type=difference_type,
        net_cash_sales=float(rollup["net_cash_sales"]),
        cash_refunds=float(rollup["cash_refunds"]),
        net_cash_movement=float(rollup["net_cash_movement"]),
        day_close_difference=float(difference_amount) if difference_amount is not None else None,
        closed_by_user_id=current_user.id,
        closed_at=now,
        created_at=now,
    )
    db.add(close_record)
    db.flush()
    db.add(
        PosCashMovement(
            tenant_id=scoped_tenant_id,
            store_id=resolved_store_id,
            cash_session_id=None,
            cashier_user_id=current_user.id,
            actor_user_id=current_user.id,
            business_date=payload.business_date,
            timezone=payload.timezone,
            sale_id=None,
            action="DAY_CLOSE",
            amount=0.0,
            expected_balance_before=None,
            expected_balance_after=None,
            transaction_id=payload.transaction_id,
            reason=payload.reason,
            trace_id=getattr(request.state, "trace_id", None),
            occurred_at=now,
            created_at=now,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "day close already exists"},
        ) from None

    response = PosCashDayCloseResponse(
        id=_normalize_uuid(close_record.id),
        tenant_id=_normalize_uuid(close_record.tenant_id),
        store_id=_normalize_uuid(close_record.store_id),
        business_date=close_record.business_date,
        timezone=close_record.timezone,
        status=close_record.status,
        force_close=close_record.force_close,
        reason=close_record.reason,
        expected_cash=Decimal(str(close_record.expected_cash)),
        counted_cash=Decimal(str(close_record.counted_cash)) if close_record.counted_cash is not None else None,
        difference_amount=Decimal(str(close_record.difference_amount))
        if close_record.difference_amount is not None
        else None,
        difference_type=close_record.difference_type,
        net_cash_sales=Decimal(str(close_record.net_cash_sales)),
        cash_refunds=Decimal(str(close_record.cash_refunds)),
        net_cash_movement=Decimal(str(close_record.net_cash_movement)),
        day_close_difference=Decimal(str(close_record.day_close_difference))
        if close_record.day_close_difference is not None
        else None,
        closed_by_user_id=_normalize_uuid(close_record.closed_by_user_id),
        closed_at=close_record.closed_at,
        created_at=close_record.created_at,
    )
    context.record_success(status_code=200, response_body=response.model_dump(mode="json"))
    action = "pos_cash_day_close.force_close" if force_close else "pos_cash_day_close.close"
    AuditService(db).record_event(
        AuditEventPayload(
            tenant_id=scoped_tenant_id,
            user_id=str(current_user.id),
            store_id=str(store.id),
            trace_id=getattr(request.state, "trace_id", None),
            actor=str(current_user.username),
            action=action,
            entity_type="pos_cash_day_close",
            entity_id=str(close_record.id),
            before={
                "open_sessions": [str(session.id) for session in open_sessions],
                "expected_cash": str(rollup["expected_cash"]),
                "net_cash_sales": str(rollup["net_cash_sales"]),
                "cash_refunds": str(rollup["cash_refunds"]),
                "net_cash_movement": str(rollup["net_cash_movement"]),
            },
            after={
                "status": close_record.status,
                "force_close": close_record.force_close,
                "business_date": str(close_record.business_date),
                "timezone": close_record.timezone,
                "expected_cash": str(rollup["expected_cash"]),
                "counted_cash": str(counted_cash) if counted_cash is not None else None,
                "difference_amount": str(difference_amount) if difference_amount is not None else None,
                "difference_type": difference_type,
                "net_cash_sales": str(rollup["net_cash_sales"]),
                "cash_refunds": str(rollup["cash_refunds"]),
                "net_cash_movement": str(rollup["net_cash_movement"]),
            },
            metadata={
                "transaction_id": payload.transaction_id,
                "reason": payload.reason,
                "open_session_count": len(open_sessions),
                "actor_role": token_data.role,
            },
            result="success",
        )
    )
    return response


@router.get("/aris3/pos/cash/day-close/summary", response_model=PosCashDayCloseSummaryListResponse, responses=POS_LIST_ERROR_RESPONSES)
def list_day_close_summary(
    store_id: str | None = None,
    business_date_from: date | None = None,
    business_date_to: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    tenant_id: Annotated[str | None, Query(description="Tenant scope. Required for superadmin roles; ignored for tenant-scoped roles.")] = None,
    token_data=Depends(get_current_token_data),
    _user=Depends(require_active_user),
    _permission=Depends(require_permission("POS_CASH_VIEW")),
    db=Depends(get_db),
):
    scoped_tenant_id = _resolve_tenant_id(token_data, tenant_id)
    store_id = _resolve_store_id(token_data, store_id)
    enforce_store_scope(token_data, store_id, db, allow_superadmin=True)

    offset = (page - 1) * page_size

    query = select(PosCashDayClose).where(PosCashDayClose.tenant_id == scoped_tenant_id)
    count_query = select(func.count()).select_from(PosCashDayClose).where(
        PosCashDayClose.tenant_id == scoped_tenant_id
    )
    if store_id:
        query = query.where(PosCashDayClose.store_id == store_id)
        count_query = count_query.where(PosCashDayClose.store_id == store_id)
    if business_date_from:
        query = query.where(PosCashDayClose.business_date >= business_date_from)
        count_query = count_query.where(PosCashDayClose.business_date >= business_date_from)
    if business_date_to:
        query = query.where(PosCashDayClose.business_date <= business_date_to)
        count_query = count_query.where(PosCashDayClose.business_date <= business_date_to)

    total = db.execute(count_query).scalar_one()
    rows = (
        db.execute(query.order_by(PosCashDayClose.business_date.desc()).limit(page_size).offset(offset))
        .scalars()
        .all()
    )
    return PosCashDayCloseSummaryListResponse(
        rows=[
            PosCashDayCloseSummaryResponse(
                id=_normalize_uuid(row.id),
                tenant_id=_normalize_uuid(row.tenant_id),
                store_id=_normalize_uuid(row.store_id),
                business_date=row.business_date,
                timezone=row.timezone,
                status=row.status,
                force_close=row.force_close,
                reason=row.reason,
                expected_cash=Decimal(str(row.expected_cash)),
                counted_cash=Decimal(str(row.counted_cash)) if row.counted_cash is not None else None,
                difference_amount=Decimal(str(row.difference_amount)) if row.difference_amount is not None else None,
                difference_type=row.difference_type,
                net_cash_sales=Decimal(str(row.net_cash_sales)),
                cash_refunds=Decimal(str(row.cash_refunds)),
                net_cash_movement=Decimal(str(row.net_cash_movement)),
                day_close_difference=Decimal(str(row.day_close_difference))
                if row.day_close_difference is not None
                else None,
                closed_by_user_id=_normalize_uuid(row.closed_by_user_id),
                closed_at=row.closed_at,
                created_at=row.created_at,
            )
            for row in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/aris3/pos/cash/reconciliation/breakdown", response_model=PosCashReconciliationBreakdownResponse, responses=POS_STANDARD_ERROR_RESPONSES, openapi_extra={
    "responses": {
        "422": {"content": {"application/json": {"example": {"code": "VALIDATION_ERROR", "message": "Validation error", "details": {"errors": [{"field": "business_date", "message": "business_date is required", "type": "value_error.missing"}]}, "trace_id": "trace-reconciliation-422"}}}}
    }
})
def reconciliation_breakdown(
    store_id: str,
    business_date: date,
    timezone: str = "UTC",
    tenant_id: Annotated[str | None, Query(description="Tenant scope. Required for superadmin roles; ignored for tenant-scoped roles.")] = None,
    token_data=Depends(get_current_token_data),
    _user=Depends(require_active_user),
    _permission=Depends(require_permission("POS_CASH_VIEW")),
    db=Depends(get_db),
):
    scoped_tenant_id = _resolve_tenant_id(token_data, tenant_id)
    store_id = _resolve_store_id(token_data, store_id)
    enforce_store_scope(token_data, store_id, db, allow_superadmin=True)

    rollup = _reconciliation_rollup(
        db,
        tenant_id=scoped_tenant_id,
        store_id=store_id,
        business_date=business_date,
    )
    day_close = (
        db.execute(
            select(PosCashDayClose).where(
                PosCashDayClose.tenant_id == scoped_tenant_id,
                PosCashDayClose.store_id == store_id,
                PosCashDayClose.business_date == business_date,
            )
        )
        .scalars()
        .first()
    )
    difference = Decimal(str(day_close.day_close_difference)) if day_close and day_close.day_close_difference else None

    movement_rows = (
        db.execute(
            select(PosCashMovement.action, func.sum(PosCashMovement.amount), func.count())
            .where(
                PosCashMovement.tenant_id == scoped_tenant_id,
                PosCashMovement.store_id == store_id,
                PosCashMovement.business_date == business_date,
            )
            .group_by(PosCashMovement.action)
        )
        .all()
    )
    movements = []
    for action, total_amount, count in movement_rows:
        movement_type = _normalize_movement_type(action)
        movements.append(
            PosCashReconciliationBreakdownRow(
                movement_type=movement_type,
                total_amount=Decimal(str(total_amount or 0)),
                movement_count=int(count or 0),
            )
        )
    return PosCashReconciliationBreakdownResponse(
        business_date=business_date,
        timezone=timezone,
        expected_cash=rollup["expected_cash"],
        opening_amount=rollup["opening_amount"],
        cash_in=rollup["cash_in"],
        cash_out=rollup["cash_out"],
        net_cash_movement=rollup["net_cash_movement"],
        net_cash_sales=rollup["net_cash_sales"],
        cash_refunds=rollup["cash_refunds"],
        day_close_difference=difference,
        movements=movements,
    )
