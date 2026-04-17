from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select

from app.aris3.core.deps import get_current_token_data, require_active_user
from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.core.scope import DEFAULT_BROAD_STORE_ROLES, enforce_store_scope, enforce_tenant_scope, is_superadmin
from app.aris3.db.models import PosAdvance, PosAdvanceEvent, PosCashMovement, PosCashSession
from app.aris3.db.session import get_db
from app.aris3.routers.pos_sales import _record_cash_movement
from app.aris3.schemas.pos_advances import (
    PosAdvanceActionRequest,
    PosAdvanceAlertsResponse,
    PosAdvanceCreateRequest,
    PosAdvanceDetailResponse,
    PosAdvanceEventResponse,
    PosAdvanceListResponse,
    PosAdvanceLookupResponse,
    PosAdvanceSummary,
    PosAdvanceSweepResponse,
)
from app.aris3.schemas.errors import ApiErrorResponse, ApiValidationErrorResponse
from app.aris3.services.pos_advances import expire_advance_if_needed, sweep_expired_advances

router = APIRouter()

POS_STANDARD_ERROR_RESPONSES = {
    401: {"description": "Unauthorized", "model": ApiErrorResponse},
    403: {"description": "Forbidden", "model": ApiErrorResponse},
    404: {"description": "Resource not found", "model": ApiErrorResponse},
    409: {"description": "Business conflict", "model": ApiErrorResponse},
    422: {"description": "Validation error", "model": ApiValidationErrorResponse},
}


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


def _summary(row: PosAdvance) -> PosAdvanceSummary:
    return PosAdvanceSummary(
        id=str(row.id),
        tenant_id=str(row.tenant_id),
        store_id=str(row.store_id),
        advance_number=row.advance_number,
        barcode_value=row.barcode_value,
        customer_name=row.customer_name,
        issued_amount=Decimal(str(row.issued_amount)),
        issued_payment_method=row.issued_payment_method,
        issued_at=row.issued_at,
        expires_at=row.expires_at,
        status=row.status,
        consumed_sale_id=str(row.consumed_sale_id) if row.consumed_sale_id else None,
        refunded_cash_movement_id=str(row.refunded_cash_movement_id) if row.refunded_cash_movement_id else None,
        refunded_at=row.refunded_at,
        expired_at=row.expired_at,
        notes=row.notes,
        created_by_user_id=str(row.created_by_user_id) if row.created_by_user_id else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _event_response(event: PosAdvanceEvent) -> PosAdvanceEventResponse:
    return PosAdvanceEventResponse(
        id=str(event.id),
        action=event.action,
        payload=event.payload,
        created_by_user_id=str(event.created_by_user_id) if event.created_by_user_id else None,
        created_at=event.created_at,
    )


def _active_session(db, *, tenant_id: str, store_id: str, cashier_user_id: str) -> PosCashSession | None:
    return (
        db.execute(
            select(PosCashSession)
            .where(
                PosCashSession.tenant_id == tenant_id,
                PosCashSession.store_id == store_id,
                PosCashSession.cashier_user_id == cashier_user_id,
                PosCashSession.status == "OPEN",
                PosCashSession.closed_at.is_(None),
            )
            .order_by(PosCashSession.opened_at.desc())
        )
        .scalars()
        .first()
    )


@router.post("/aris3/pos/advances", response_model=PosAdvanceDetailResponse, responses=POS_STANDARD_ERROR_RESPONSES)
def create_advance(
    payload: PosAdvanceCreateRequest,
    request: Request,
    db=Depends(get_db),
    current_user=Depends(require_active_user),
    token_data=Depends(get_current_token_data),
):
    tenant_id = _resolve_tenant_id(token_data, None)
    store_id = _resolve_store_id(token_data, payload.store_id)
    enforce_tenant_scope(token_data, tenant_id)
    enforce_store_scope(token_data, store_id, db)

    if payload.amount <= 0:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "amount must be greater than 0"})

    now = datetime.utcnow()
    next_number = int(
        db.execute(
            select(func.coalesce(func.max(PosAdvance.advance_number), 0)).where(
                PosAdvance.tenant_id == tenant_id,
                PosAdvance.store_id == store_id,
            )
        ).scalar_one()
        or 0
    ) + 1
    barcode = f"ADV-{str(store_id).replace('-', '')[:8]}-{next_number:08d}"

    row = PosAdvance(
        tenant_id=UUID(tenant_id),
        store_id=UUID(store_id),
        advance_number=next_number,
        barcode_value=barcode,
        customer_name=payload.customer_name.strip(),
        issued_amount=payload.amount,
        issued_payment_method=payload.payment_method,
        issued_at=now,
        expires_at=now + timedelta(days=60),
        status="ACTIVE",
        notes=payload.notes,
        created_by_user_id=current_user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.flush()
    db.add(
        PosAdvanceEvent(
            advance_id=row.id,
            tenant_id=row.tenant_id,
            store_id=row.store_id,
            action="ISSUED",
            payload={"transaction_id": payload.transaction_id, "payment_method": payload.payment_method},
            created_by_user_id=current_user.id,
            created_at=now,
        )
    )

    if payload.payment_method == "CASH":
        session = _active_session(db, tenant_id=tenant_id, store_id=store_id, cashier_user_id=str(current_user.id))
        if session:
            _record_cash_movement(
                db,
                session=session,
                tenant_id=tenant_id,
                store_id=store_id,
                sale_id=row.id,
                action="CASH_IN",
                amount=Decimal(str(payload.amount)),
                transaction_id=payload.transaction_id,
                actor_user_id=str(current_user.id),
                trace_id=getattr(request.state, "trace_id", None),
                occurred_at=now,
            )

    db.commit()
    events = db.execute(select(PosAdvanceEvent).where(PosAdvanceEvent.advance_id == row.id).order_by(PosAdvanceEvent.created_at)).scalars().all()
    response = PosAdvanceDetailResponse(**_summary(row).model_dump(), events=[_event_response(e) for e in events])
    return response


@router.get("/aris3/pos/advances", response_model=PosAdvanceListResponse, responses=POS_STANDARD_ERROR_RESPONSES)
def list_advances(
    request: Request,
    tenant_id: str | None = Query(default=None),
    store_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db=Depends(get_db),
    current_user=Depends(require_active_user),
    token_data=Depends(get_current_token_data),
):
    scoped_tenant = _resolve_tenant_id(token_data, tenant_id)
    scoped_store = _resolve_store_id(token_data, store_id)
    enforce_tenant_scope(token_data, scoped_tenant)
    enforce_store_scope(token_data, scoped_store, db)

    sweep_expired_advances(db, tenant_id=scoped_tenant, store_id=scoped_store)
    db.commit()

    query = select(PosAdvance).where(PosAdvance.tenant_id == scoped_tenant, PosAdvance.store_id == scoped_store)
    if status:
        query = query.where(PosAdvance.status == status.upper())
    if q:
        like = f"%{q}%"
        query = query.where(or_(PosAdvance.customer_name.ilike(like), PosAdvance.barcode_value.ilike(like)))

    total = int(db.execute(select(func.count()).select_from(query.subquery())).scalar_one() or 0)
    rows = db.execute(query.order_by(PosAdvance.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return PosAdvanceListResponse(page=page, page_size=page_size, total=total, rows=[_summary(r) for r in rows])


@router.get("/aris3/pos/advances/lookup", response_model=PosAdvanceLookupResponse, responses=POS_STANDARD_ERROR_RESPONSES)
def lookup_advance(
    code: str,
    request: Request,
    db=Depends(get_db),
    current_user=Depends(require_active_user),
    token_data=Depends(get_current_token_data),
):
    row = db.execute(select(PosAdvance).where(PosAdvance.barcode_value == code)).scalars().first()
    if not row:
        return PosAdvanceLookupResponse(found=False, advance=None)
    enforce_tenant_scope(token_data, str(row.tenant_id))
    enforce_store_scope(token_data, str(row.store_id), db)
    changed = expire_advance_if_needed(db, row, actor_user_id=str(current_user.id))
    db.add(
        PosAdvanceEvent(
            advance_id=row.id,
            tenant_id=row.tenant_id,
            store_id=row.store_id,
            action="VALIDATED",
            payload={"code": code, "status": row.status},
            created_by_user_id=current_user.id,
            created_at=datetime.utcnow(),
        )
    )
    db.commit()
    return PosAdvanceLookupResponse(found=True, advance=_summary(row))


@router.get("/aris3/pos/advances/alerts", response_model=PosAdvanceAlertsResponse, responses=POS_STANDARD_ERROR_RESPONSES)
def alerts_advances(
    request: Request,
    days: int = Query(default=5, ge=1, le=30),
    tenant_id: str | None = Query(default=None),
    store_id: str | None = Query(default=None),
    db=Depends(get_db),
    current_user=Depends(require_active_user),
    token_data=Depends(get_current_token_data),
):
    scoped_tenant = _resolve_tenant_id(token_data, tenant_id)
    scoped_store = _resolve_store_id(token_data, store_id)
    enforce_tenant_scope(token_data, scoped_tenant)
    enforce_store_scope(token_data, scoped_store, db)

    now = datetime.utcnow()
    window_end = now + timedelta(days=days)
    sweep_expired_advances(db, tenant_id=scoped_tenant, store_id=scoped_store, actor_user_id=str(current_user.id), now=now)
    db.commit()
    rows = db.execute(
        select(PosAdvance)
        .where(
            PosAdvance.tenant_id == scoped_tenant,
            PosAdvance.store_id == scoped_store,
            PosAdvance.status == "ACTIVE",
            PosAdvance.expires_at >= now,
            PosAdvance.expires_at <= window_end,
        )
        .order_by(PosAdvance.expires_at.asc())
    ).scalars().all()
    return PosAdvanceAlertsResponse(as_of=now, days=days, total=len(rows), rows=[_summary(r) for r in rows])


@router.get("/aris3/pos/advances/{advance_id}", response_model=PosAdvanceDetailResponse, responses=POS_STANDARD_ERROR_RESPONSES)
def get_advance(
    advance_id: str,
    request: Request,
    db=Depends(get_db),
    current_user=Depends(require_active_user),
    token_data=Depends(get_current_token_data),
):
    row = db.execute(select(PosAdvance).where(PosAdvance.id == advance_id)).scalars().first()
    if not row:
        raise AppError(ErrorCatalog.RESOURCE_NOT_FOUND, details={"message": "advance not found"})
    enforce_tenant_scope(token_data, str(row.tenant_id))
    enforce_store_scope(token_data, str(row.store_id), db)
    if expire_advance_if_needed(db, row, actor_user_id=str(current_user.id)):
        db.commit()
    events = db.execute(select(PosAdvanceEvent).where(PosAdvanceEvent.advance_id == row.id).order_by(PosAdvanceEvent.created_at)).scalars().all()
    return PosAdvanceDetailResponse(**_summary(row).model_dump(), events=[_event_response(e) for e in events])


@router.post("/aris3/pos/advances/{advance_id}/actions", response_model=PosAdvanceDetailResponse, responses=POS_STANDARD_ERROR_RESPONSES)
def mutate_advance(
    advance_id: str,
    payload: PosAdvanceActionRequest,
    request: Request,
    db=Depends(get_db),
    current_user=Depends(require_active_user),
    token_data=Depends(get_current_token_data),
):
    row = db.execute(select(PosAdvance).where(PosAdvance.id == advance_id).with_for_update()).scalars().first()
    if not row:
        raise AppError(ErrorCatalog.RESOURCE_NOT_FOUND, details={"message": "advance not found"})
    enforce_tenant_scope(token_data, str(row.tenant_id))
    enforce_store_scope(token_data, str(row.store_id), db)

    expire_advance_if_needed(db, row, actor_user_id=str(current_user.id))
    if row.status in {"CONSUMED", "REFUNDED", "EXPIRED"}:
        raise AppError(ErrorCatalog.BUSINESS_CONFLICT, details={"message": "advance is terminal", "status": row.status})

    now = datetime.utcnow()
    if payload.action == "REFUND":
        if not payload.refund_method:
            raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "refund_method is required"})
        movement_id = None
        if payload.refund_method == "CASH":
            session = _active_session(db, tenant_id=str(row.tenant_id), store_id=str(row.store_id), cashier_user_id=str(current_user.id))
            if session is None:
                raise AppError(ErrorCatalog.BUSINESS_CONFLICT, details={"message": "open cash session required for CASH refund"})
            _record_cash_movement(
                db,
                session=session,
                tenant_id=str(row.tenant_id),
                store_id=str(row.store_id),
                sale_id=row.id,
                action="CASH_OUT",
                amount=Decimal(str(row.issued_amount)),
                transaction_id=payload.transaction_id,
                actor_user_id=str(current_user.id),
                trace_id=getattr(request.state, "trace_id", None),
                occurred_at=now,
            )
            movement = db.execute(select(PosCashMovement).where(PosCashMovement.transaction_id == payload.transaction_id).order_by(PosCashMovement.created_at.desc())).scalars().first()
            movement_id = movement.id if movement else None
        row.status = "REFUNDED"
        row.refunded_cash_movement_id = movement_id
        row.refunded_at = now
        row.updated_at = now
        action = "REFUNDED"
        event_payload = {"refund_method": payload.refund_method, "transaction_id": payload.transaction_id, "reason": payload.reason}
    else:
        row.status = "EXPIRED"
        row.expired_at = now
        row.updated_at = now
        action = "EXPIRED"
        event_payload = {"trigger": "manual", "transaction_id": payload.transaction_id, "reason": payload.reason}

    db.add(
        PosAdvanceEvent(
            advance_id=row.id,
            tenant_id=row.tenant_id,
            store_id=row.store_id,
            action=action,
            payload=event_payload,
            created_by_user_id=current_user.id,
            created_at=now,
        )
    )
    db.commit()
    events = db.execute(select(PosAdvanceEvent).where(PosAdvanceEvent.advance_id == row.id).order_by(PosAdvanceEvent.created_at)).scalars().all()
    return PosAdvanceDetailResponse(**_summary(row).model_dump(), events=[_event_response(e) for e in events])


@router.post("/aris3/pos/advances/actions/sweep-expired", response_model=PosAdvanceSweepResponse, responses=POS_STANDARD_ERROR_RESPONSES)
def sweep_endpoint(
    request: Request,
    tenant_id: str | None = Query(default=None),
    store_id: str | None = Query(default=None),
    db=Depends(get_db),
    current_user=Depends(require_active_user),
    token_data=Depends(get_current_token_data),
):
    scoped_tenant = _resolve_tenant_id(token_data, tenant_id)
    scoped_store = _resolve_store_id(token_data, store_id)
    enforce_tenant_scope(token_data, scoped_tenant)
    enforce_store_scope(token_data, scoped_store, db)
    now = datetime.utcnow()
    rows = sweep_expired_advances(db, tenant_id=scoped_tenant, store_id=scoped_store, actor_user_id=str(current_user.id), now=now)
    db.commit()
    return PosAdvanceSweepResponse(expired_count=len(rows), expired_ids=[str(r.id) for r in rows], as_of=now)
