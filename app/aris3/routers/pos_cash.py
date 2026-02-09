from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from app.aris3.core.deps import get_current_token_data, require_active_user, require_permission
from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.core.scope import DEFAULT_BROAD_STORE_ROLES, enforce_store_scope, enforce_tenant_scope, is_superadmin
from app.aris3.db.models import PosCashDayClose, PosCashMovement, PosCashSession
from app.aris3.db.session import get_db
from app.aris3.schemas.pos_cash import (
    PosCashDayCloseActionRequest,
    PosCashDayCloseResponse,
    PosCashMovementListResponse,
    PosCashMovementResponse,
    PosCashSessionActionRequest,
    PosCashSessionCurrentResponse,
    PosCashSessionSummary,
)
from app.aris3.services.audit import AuditEventPayload, AuditService
from app.aris3.services.idempotency import IdempotencyService, extract_idempotency_key


router = APIRouter()


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
        cash_session_id=_normalize_uuid(movement.cash_session_id),
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
        created_at=movement.created_at,
    )


def _open_session_query(db, *, tenant_id: str, store_id: str, cashier_user_id: str, for_update: bool = False):
    query = select(PosCashSession).where(
        PosCashSession.tenant_id == tenant_id,
        PosCashSession.store_id == store_id,
        PosCashSession.cashier_user_id == cashier_user_id,
        PosCashSession.status == "OPEN",
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


@router.get("/aris3/pos/cash/session/current", response_model=PosCashSessionCurrentResponse)
def get_current_session(
    store_id: str | None = None,
    cashier_user_id: str | None = None,
    tenant_id: str | None = None,
    token_data=Depends(get_current_token_data),
    _user=Depends(require_active_user),
    _permission=Depends(require_permission("POS_CASH_VIEW")),
    db=Depends(get_db),
):
    scoped_tenant_id = _resolve_tenant_id(token_data, tenant_id)
    if not store_id:
        store_id = token_data.store_id
    if not store_id:
        raise AppError(ErrorCatalog.STORE_SCOPE_REQUIRED)
    enforce_store_scope(token_data, store_id, db, allow_superadmin=True)
    if not cashier_user_id:
        cashier_user_id = token_data.sub
    session = _open_session_query(
        db,
        tenant_id=scoped_tenant_id,
        store_id=store_id,
        cashier_user_id=cashier_user_id,
        for_update=False,
    )
    return PosCashSessionCurrentResponse(session=_session_summary(session) if session else None)


@router.post("/aris3/pos/cash/session/actions", response_model=PosCashSessionSummary)
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
    store = enforce_store_scope(token_data, payload.store_id, db, allow_superadmin=True)

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
        existing = _open_session_query(
            db,
            tenant_id=scoped_tenant_id,
            store_id=payload.store_id,
            cashier_user_id=cashier_user_id,
            for_update=True,
        )
        if existing:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "open cash session already exists"},
            )

        session = PosCashSession(
            tenant_id=scoped_tenant_id,
            store_id=payload.store_id,
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
        db.add(
            PosCashMovement(
                tenant_id=scoped_tenant_id,
                store_id=payload.store_id,
                cash_session_id=session.id,
                cashier_user_id=current_user.id,
                business_date=payload.business_date,
                timezone=payload.timezone,
                sale_id=None,
                action="OPEN",
                amount=float(opening_amount),
                expected_balance_before=0.0,
                expected_balance_after=float(opening_amount),
                transaction_id=payload.transaction_id,
                reason=payload.reason,
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
        store_id=payload.store_id,
        cashier_user_id=cashier_user_id,
        for_update=True,
    )
    if not session:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "open cash session required"},
        )
    if session.status != "OPEN":
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "cash session is not open"},
        )

    expected_before = Decimal(str(session.expected_cash or 0))

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
    else:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "unsupported action"})

    db.add(
        PosCashMovement(
            tenant_id=scoped_tenant_id,
            store_id=payload.store_id,
            cash_session_id=session.id,
            cashier_user_id=session.cashier_user_id,
            business_date=session.business_date,
            timezone=session.timezone,
            sale_id=None,
            action=movement_action,
            amount=float(movement_amount),
            expected_balance_before=float(expected_before),
            expected_balance_after=float(expected_after),
            transaction_id=payload.transaction_id,
            reason=payload.reason,
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
            },
            after={
                "status": status_after,
                "expected_cash": str(expected_after),
                "counted_cash": str(counted_cash) if counted_cash is not None else None,
                "difference": str(difference) if difference is not None else None,
            },
            metadata={"transaction_id": payload.transaction_id, "reason": payload.reason},
            result="success",
        )
    )
    return response


@router.get("/aris3/pos/cash/movements", response_model=PosCashMovementListResponse)
def list_cash_movements(
    store_id: str | None = None,
    cashier_user_id: str | None = None,
    movement_type: str | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
    tenant_id: str | None = None,
    token_data=Depends(get_current_token_data),
    _user=Depends(require_active_user),
    _permission=Depends(require_permission("POS_CASH_VIEW")),
    db=Depends(get_db),
):
    scoped_tenant_id = _resolve_tenant_id(token_data, tenant_id)
    if token_data.store_id and token_data.role.upper() not in {role.upper() for role in DEFAULT_BROAD_STORE_ROLES}:
        store_id = token_data.store_id
    if store_id:
        enforce_store_scope(token_data, store_id, db, allow_superadmin=True)

    limit = max(1, min(limit, 500))
    offset = max(0, offset)

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
    if from_ts:
        query = query.where(PosCashMovement.created_at >= from_ts)
        count_query = count_query.where(PosCashMovement.created_at >= from_ts)
    if to_ts:
        query = query.where(PosCashMovement.created_at <= to_ts)
        count_query = count_query.where(PosCashMovement.created_at <= to_ts)

    total = db.execute(count_query).scalar_one()
    rows = db.execute(query.order_by(PosCashMovement.created_at.desc()).limit(limit).offset(offset)).scalars().all()
    return PosCashMovementListResponse(rows=[_movement_response(row) for row in rows], total=total)


@router.post("/aris3/pos/cash/day-close/actions", response_model=PosCashDayCloseResponse)
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
    store = enforce_store_scope(token_data, payload.store_id, db, allow_superadmin=True)

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
                PosCashDayClose.store_id == payload.store_id,
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
                PosCashSession.store_id == payload.store_id,
                PosCashSession.business_date == payload.business_date,
                PosCashSession.status == "OPEN",
            )
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

    now = datetime.utcnow()
    close_record = PosCashDayClose(
        tenant_id=scoped_tenant_id,
        store_id=payload.store_id,
        business_date=payload.business_date,
        timezone=payload.timezone,
        status="CLOSED",
        force_close=force_close,
        reason=payload.reason,
        closed_by_user_id=current_user.id,
        closed_at=now,
        created_at=now,
    )
    db.add(close_record)
    db.commit()

    response = PosCashDayCloseResponse(
        id=_normalize_uuid(close_record.id),
        tenant_id=_normalize_uuid(close_record.tenant_id),
        store_id=_normalize_uuid(close_record.store_id),
        business_date=close_record.business_date,
        timezone=close_record.timezone,
        status=close_record.status,
        force_close=close_record.force_close,
        reason=close_record.reason,
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
            before={"open_sessions": [str(session.id) for session in open_sessions]},
            after={
                "status": close_record.status,
                "force_close": close_record.force_close,
                "business_date": str(close_record.business_date),
                "timezone": close_record.timezone,
            },
            metadata={
                "transaction_id": payload.transaction_id,
                "reason": payload.reason,
                "open_session_count": len(open_sessions),
            },
            result="success",
        )
    )
    return response
