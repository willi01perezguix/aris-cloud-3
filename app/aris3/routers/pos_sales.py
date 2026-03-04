from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import delete, func, or_, select

from app.aris3.core.context import build_request_context
from app.aris3.core.deps import get_current_token_data, require_active_user, require_permission
from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.core.scope import (
    DEFAULT_BROAD_STORE_ROLES,
    enforce_store_scope,
    enforce_tenant_scope,
    is_superadmin,
)
from app.aris3.db.models import (
    PosCashDayClose,
    PosCashMovement,
    PosCashSession,
    PosPayment,
    PosReturnEvent,
    PosSale,
    PosSaleLine,
    ReturnPolicySettings,
    StockItem,
)
from app.aris3.db.session import get_db
from app.aris3.repos.pos_sales import PosSaleQueryFilters, PosSaleRepository
from app.aris3.repos.settings import ReturnPolicySettingsRepository
from app.aris3.schemas.errors import ApiErrorResponse, ApiValidationErrorResponse
from app.aris3.schemas.pos_sales import (
    PosPaymentCreate,
    PosPaymentResponse,
    PosPaymentSummary,
    PosReturnEventSummary,
    PosReturnItem,
    PosReturnTotals,
    PosSaleActionRequest,
    PosSaleCreateRequest,
    PosSaleHeaderResponse,
    PosSaleLineCreate,
    PosSaleLineResponse,
    PosSaleLineSnapshot,
    PosSaleListResponse,
    PosSaleResponse,
    PosSaleUpdateRequest,
)
from app.aris3.services.access_control import AccessControlService
from app.aris3.services.audit import AuditEventPayload, AuditService
from app.aris3.services.idempotency import IdempotencyService, extract_idempotency_key


router = APIRouter()


POS_STANDARD_ERROR_RESPONSES = {
    401: {"description": "Unauthorized", "model": ApiErrorResponse},
    403: {"description": "Forbidden", "model": ApiErrorResponse},
    404: {"description": "Resource not found", "model": ApiErrorResponse},
    409: {"description": "Business conflict", "model": ApiErrorResponse},
    422: {"description": "Validation error", "model": ApiValidationErrorResponse},
}


def _require_transaction_id(transaction_id: str | None) -> None:
    if not transaction_id:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "transaction_id is required"},
        )


def _normalize_uuid(value: str | UUID) -> str:
    return str(value)


def _parse_filter_date(value: date | None, *, end_of_day: bool = False) -> datetime | None:
    if value is None:
        return None
    if end_of_day:
        return datetime.combine(value, time.max)
    return datetime.combine(value, time.min)


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
    locked_store = token_data.store_id
    broad_roles = {role.upper() for role in DEFAULT_BROAD_STORE_ROLES}
    if locked_store and token_data.role.upper() not in broad_roles:
        if requested_store_id and requested_store_id != locked_store:
            raise AppError(ErrorCatalog.STORE_SCOPE_MISMATCH)
        return locked_store
    if requested_store_id:
        return requested_store_id
    if locked_store:
        return locked_store
    raise AppError(ErrorCatalog.STORE_SCOPE_REQUIRED)


def _authoritative_price(stock: StockItem, fallback: Decimal) -> Decimal:
    if stock.sale_price is not None:
        return Decimal(str(stock.sale_price)).quantize(Decimal("0.01"))
    return fallback.quantize(Decimal("0.01"))


def _build_sale_line_from_stock(db, *, tenant_id: str, line: PosSaleLineCreate, store_id: str) -> PosSaleLineCreate:
    _validate_sale_snapshot(line)
    snapshot = line.snapshot
    if line.line_type == "EPC":
        stock = (
            db.execute(
                select(StockItem).where(
                    StockItem.tenant_id == tenant_id,
                    StockItem.epc == snapshot.epc,
                    StockItem.location_code == snapshot.location_code,
                    StockItem.pool == snapshot.pool,
                    StockItem.status == "RFID",
                    StockItem.location_is_vendible.is_(True),
                )
            )
            .scalars()
            .first()
        )
        if not stock:
            raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "epc not available for sale", "epc": snapshot.epc})
        expected_price = _authoritative_price(stock, line.unit_price)
        if line.unit_price.quantize(Decimal("0.01")) != expected_price:
            raise AppError(ErrorCatalog.BUSINESS_CONFLICT, details={"message": "unit_price mismatch", "expected": str(expected_price), "received": str(line.unit_price)})
        rebuilt_snapshot = PosSaleLineSnapshot(
            sku=stock.sku,
            description=stock.description,
            var1_value=stock.var1_value,
            var2_value=stock.var2_value,
            epc=stock.epc,
            location_code=stock.location_code,
            pool=stock.pool,
            status=stock.status,
            location_is_vendible=bool(stock.location_is_vendible),
            image_asset_id=stock.image_asset_id,
            image_url=stock.image_url,
            image_thumb_url=stock.image_thumb_url,
            image_source=stock.image_source,
            image_updated_at=stock.image_updated_at,
        )
        return PosSaleLineCreate(line_type=line.line_type, qty=1, unit_price=expected_price, snapshot=rebuilt_snapshot)

    count = db.execute(select(func.count()).select_from(StockItem).where(
        StockItem.tenant_id == tenant_id,
        StockItem.sku == snapshot.sku,
        StockItem.location_code == snapshot.location_code,
        StockItem.pool == snapshot.pool,
        StockItem.status == "PENDING",
        StockItem.location_is_vendible.is_(True),
    )).scalar_one()
    if int(count or 0) < line.qty:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "insufficient stock for sku", "sku": snapshot.sku})
    stock = (
        db.execute(select(StockItem).where(
            StockItem.tenant_id == tenant_id,
            StockItem.sku == snapshot.sku,
            StockItem.location_code == snapshot.location_code,
            StockItem.pool == snapshot.pool,
            StockItem.status == "PENDING",
            StockItem.location_is_vendible.is_(True),
        ).order_by(StockItem.created_at))
        .scalars()
        .first()
    )
    if not stock:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "sku not available for sale", "sku": snapshot.sku})
    expected_price = _authoritative_price(stock, line.unit_price)
    if line.unit_price.quantize(Decimal("0.01")) != expected_price:
        raise AppError(ErrorCatalog.BUSINESS_CONFLICT, details={"message": "unit_price mismatch", "expected": str(expected_price), "received": str(line.unit_price), "sku": snapshot.sku})
    rebuilt_snapshot = PosSaleLineSnapshot(
        sku=stock.sku,
        description=stock.description,
        var1_value=stock.var1_value,
        var2_value=stock.var2_value,
        epc=None,
        location_code=stock.location_code,
        pool=stock.pool,
        status=stock.status,
        location_is_vendible=bool(stock.location_is_vendible),
        image_asset_id=stock.image_asset_id,
        image_url=stock.image_url,
        image_thumb_url=stock.image_thumb_url,
        image_source=stock.image_source,
        image_updated_at=stock.image_updated_at,
    )
    return PosSaleLineCreate(line_type=line.line_type, qty=line.qty, unit_price=expected_price, snapshot=rebuilt_snapshot)


def _validate_sale_snapshot(line: PosSaleLineCreate) -> None:
    snapshot = line.snapshot
    if line.qty < 1:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "qty must be at least 1", "qty": line.qty},
        )
    if line.unit_price < 0:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "unit_price must be >= 0", "unit_price": str(line.unit_price)},
        )
    if line.line_type == "EPC":
        if line.qty != 1:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "qty must be 1 for EPC lines", "qty": line.qty},
            )
        if not snapshot.epc:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "epc is required for EPC lines"},
            )
    if line.line_type == "SKU" and snapshot.epc is not None:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "epc must be empty for SKU lines"},
        )
    if not snapshot.location_code or not snapshot.pool:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "location_code and pool are required in line snapshot"},
        )


def _line_total(line: PosSaleLineCreate) -> Decimal:
    return (line.unit_price * Decimal(line.qty)).quantize(Decimal("0.01"))


def _sale_totals(lines: list[PosSaleLineCreate]) -> dict[str, Decimal]:
    total_due = sum((_line_total(line) for line in lines), Decimal("0.00"))
    return {
        "total_due": total_due,
        "paid_total": Decimal("0.00"),
        "balance_due": total_due,
        "change_due": Decimal("0.00"),
    }


def _payment_summary(payments: list[PosPayment]) -> list[PosPaymentSummary]:
    totals: dict[str, Decimal] = {}
    for payment in payments:
        totals[payment.method] = totals.get(payment.method, Decimal("0.00")) + Decimal(str(payment.amount))
    return [PosPaymentSummary(method=method, amount=amount) for method, amount in totals.items()]


def _record_cash_movement(
    db,
    *,
    session: PosCashSession,
    tenant_id: str,
    store_id: str,
    sale_id: uuid.UUID,
    action: str,
    amount: Decimal,
    transaction_id: str | None,
    actor_user_id: str | None,
    trace_id: str | None,
    occurred_at: datetime,
) -> None:
    if amount <= 0:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "cash movement amount must be greater than 0"},
        )
    existing_day_close = (
        db.execute(
            select(PosCashDayClose).where(
                PosCashDayClose.tenant_id == tenant_id,
                PosCashDayClose.store_id == store_id,
                PosCashDayClose.business_date == session.business_date,
            )
        )
        .scalars()
        .first()
    )
    if existing_day_close:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "cash movements are locked after day close"},
        )

    expected_before = Decimal(str(session.expected_cash or 0))
    if action in {"SALE"}:
        expected_after = expected_before + amount
    else:
        expected_after = expected_before - amount
    if expected_after < 0:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "cash_out would result in negative expected balance"},
        )
    session.expected_cash = float(expected_after)
    db.add(
        PosCashMovement(
            tenant_id=tenant_id,
            store_id=store_id,
            cash_session_id=session.id,
            cashier_user_id=session.cashier_user_id,
            actor_user_id=actor_user_id,
            business_date=session.business_date,
            timezone=session.timezone,
            sale_id=sale_id,
            action=action,
            amount=float(amount),
            expected_balance_before=float(expected_before),
            expected_balance_after=float(expected_after),
            transaction_id=transaction_id,
            trace_id=trace_id,
            occurred_at=occurred_at,
        )
    )


def _validate_payments(payments: list[PosPaymentCreate], total_due: Decimal) -> dict[str, Decimal]:
    if not payments:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "payments must not be empty for checkout"},
        )

    paid_total = Decimal("0.00")
    cash_total = Decimal("0.00")
    non_cash_total = Decimal("0.00")
    for payment in payments:
        if payment.amount <= 0:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "payment amount must be greater than 0"},
            )
        if payment.method == "CARD" and not payment.authorization_code:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "authorization_code is required for CARD"},
            )
        if payment.method == "TRANSFER":
            if not payment.bank_name or not payment.voucher_number:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "bank_name and voucher_number are required for TRANSFER"},
                )

        paid_total += payment.amount
        if payment.method == "CASH":
            cash_total += payment.amount
        else:
            non_cash_total += payment.amount

    if paid_total < total_due:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "paid_total is less than total_due", "paid_total": str(paid_total)},
        )
    change_due = paid_total - total_due
    if change_due > 0 and cash_total <= 0:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "change_due requires CASH component"},
        )
    if change_due > cash_total:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "change_due exceeds CASH component", "change_due": str(change_due)},
        )
    if non_cash_total > total_due:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "non-cash payments exceed total_due"},
        )
    return {
        "total_due": total_due,
        "paid_total": paid_total,
        "balance_due": max(total_due - paid_total, Decimal("0.00")),
        "change_due": change_due,
        "cash_total": cash_total,
    }


def _default_return_policy() -> ReturnPolicySettings:
    return ReturnPolicySettings(
        tenant_id=uuid.UUID(int=0),
        return_window_days=30,
        require_receipt=True,
        allow_refund_cash=True,
        allow_refund_card=True,
        allow_refund_transfer=True,
        allow_exchange=True,
        require_manager_for_exceptions=False,
        accepted_conditions=["NEW", "GOOD", "USED"],
        non_reusable_label_strategy="ASSIGN_NEW_EPC",
        restocking_fee_pct=0.0,
    )


def _get_return_policy(db, tenant_id: str) -> ReturnPolicySettings:
    settings = ReturnPolicySettingsRepository(db).get_by_tenant_id(tenant_id)
    return settings or _default_return_policy()


def _policy_snapshot(policy: ReturnPolicySettings) -> dict:
    return {
        "return_window_days": policy.return_window_days,
        "require_receipt": policy.require_receipt,
        "allow_refund_cash": policy.allow_refund_cash,
        "allow_refund_card": policy.allow_refund_card,
        "allow_refund_transfer": policy.allow_refund_transfer,
        "allow_exchange": policy.allow_exchange,
        "require_manager_for_exceptions": policy.require_manager_for_exceptions,
        "accepted_conditions": policy.accepted_conditions or [],
        "non_reusable_label_strategy": policy.non_reusable_label_strategy,
        "restocking_fee_pct": policy.restocking_fee_pct,
    }


def _require_action_permission(request: Request, token_data, db, permission: str) -> None:
    context = getattr(request.state, "context", None)
    if context is None:
        context = build_request_context(
            user_id=token_data.sub,
            tenant_id=token_data.tenant_id,
            store_id=token_data.store_id,
            role=token_data.role,
            trace_id=getattr(request.state, "trace_id", ""),
        )
        request.state.context = context
    service = AccessControlService(db, cache=getattr(request.state, "permission_cache", None))
    decision = service.evaluate_permission(permission, context, token_data)
    if not decision.allowed:
        raise AppError(ErrorCatalog.PERMISSION_DENIED)


def _refund_totals(subtotal: Decimal, restocking_fee_pct: Decimal) -> dict[str, Decimal]:
    restocking_fee = (subtotal * restocking_fee_pct / Decimal("100.0")).quantize(Decimal("0.01"))
    total = (subtotal - restocking_fee).quantize(Decimal("0.01"))
    return {"subtotal": subtotal, "restocking_fee": restocking_fee, "total": total}


def _return_event_summaries(events: list[PosReturnEvent]) -> tuple[PosReturnTotals, PosReturnTotals, Decimal, list[PosReturnEventSummary]]:
    refund_subtotal = Decimal("0.00")
    restocking_fee = Decimal("0.00")
    refund_total = Decimal("0.00")
    exchange_total = Decimal("0.00")
    net_adjustment = Decimal("0.00")
    summaries: list[PosReturnEventSummary] = []
    for event in events:
        refund_subtotal += Decimal(str(event.refund_subtotal or 0))
        restocking_fee += Decimal(str(event.restocking_fee or 0))
        refund_total += Decimal(str(event.refund_total or 0))
        exchange_total += Decimal(str(event.exchange_total or 0))
        net_adjustment += Decimal(str(event.net_adjustment or 0))
        summaries.append(
            PosReturnEventSummary(
                id=_normalize_uuid(event.id),
                action=event.action,
                refund_total=Decimal(str(event.refund_total or 0)),
                exchange_total=Decimal(str(event.exchange_total or 0)),
                net_adjustment=Decimal(str(event.net_adjustment or 0)),
                created_at=event.created_at,
            )
        )
    refund_totals = PosReturnTotals(
        subtotal=refund_subtotal,
        restocking_fee=restocking_fee,
        total=refund_total,
    )
    exchange_totals = PosReturnTotals(
        subtotal=exchange_total,
        restocking_fee=Decimal("0.00"),
        total=exchange_total,
    )
    return refund_totals, exchange_totals, net_adjustment, summaries


def _refunded_quantities(events: list[PosReturnEvent]) -> dict[str, int]:
    refunded: dict[str, int] = {}
    for event in events:
        payload = event.payload or {}
        for item in payload.get("returned_lines", []):
            line_id = item.get("line_id")
            qty = item.get("qty", 0)
            if not line_id:
                continue
            refunded[line_id] = refunded.get(line_id, 0) + int(qty)
    return refunded


def _require_manager_override(
    current_user,
    *,
    policy: ReturnPolicySettings,
    exceptions: list[str],
    manager_override: bool | None,
) -> None:
    if not exceptions:
        return
    if not policy.require_manager_for_exceptions:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "return policy exception not allowed", "exceptions": exceptions},
        )
    if not manager_override:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "manager override required", "exceptions": exceptions},
        )
    role = (current_user.role or "").upper()
    if role not in {"MANAGER", "ADMIN", "SUPERADMIN", "PLATFORM_ADMIN"}:
        raise AppError(
            ErrorCatalog.PERMISSION_DENIED,
            details={"message": "manager override requires elevated role"},
        )


def _require_open_cash_session(db, *, tenant_id: str, store_id: str, cashier_user_id: str) -> PosCashSession:
    session = (
        db.execute(
            select(PosCashSession).where(
                PosCashSession.tenant_id == tenant_id,
                PosCashSession.store_id == store_id,
                PosCashSession.cashier_user_id == cashier_user_id,
                PosCashSession.status == "OPEN",
            )
            .with_for_update()
        )
        .scalars()
        .first()
    )
    if session is None:
        raise AppError(
            ErrorCatalog.BUSINESS_CONFLICT,
            details={"message": "open cash session required for CASH payments"},
        )
    return session


def _sale_line_response(line: PosSaleLine, *, returned_qty: int = 0) -> PosSaleLineResponse:
    snapshot = PosSaleLineSnapshot(
        sku=line.sku,
        description=line.description,
        var1_value=line.var1_value,
        var2_value=line.var2_value,
        epc=line.epc,
        location_code=line.location_code,
        pool=line.pool,
        status=line.status,
        location_is_vendible=line.location_is_vendible,
        image_asset_id=line.image_asset_id,
        image_url=line.image_url,
        image_thumb_url=line.image_thumb_url,
        image_source=line.image_source,
        image_updated_at=line.image_updated_at,
    )
    return PosSaleLineResponse(
        id=_normalize_uuid(line.id),
        line_type=line.line_type,
        qty=line.qty,
        unit_price=Decimal(str(line.unit_price)),
        line_total=Decimal(str(line.line_total)),
        returned_qty=returned_qty,
        returnable_qty=max(int(line.qty) - returned_qty, 0),
        snapshot=snapshot,
        created_at=line.created_at,
    )


def _payment_response(payment: PosPayment) -> PosPaymentResponse:
    return PosPaymentResponse(
        id=_normalize_uuid(payment.id),
        method=payment.method,
        amount=Decimal(str(payment.amount)),
        authorization_code=payment.authorization_code,
        bank_name=payment.bank_name,
        voucher_number=payment.voucher_number,
        created_at=payment.created_at,
    )


def _sale_response(repo: PosSaleRepository, sale: PosSale) -> PosSaleResponse:
    lines = repo.get_lines(_normalize_uuid(sale.id))
    payments = repo.get_payments(_normalize_uuid(sale.id))
    return_events = repo.get_return_events(_normalize_uuid(sale.id))
    refunded_totals, exchanged_totals, net_adjustment, return_summaries = _return_event_summaries(return_events)
    refunded_quantities = _refunded_quantities(return_events)
    header = PosSaleHeaderResponse(
        id=_normalize_uuid(sale.id),
        tenant_id=_normalize_uuid(sale.tenant_id),
        store_id=_normalize_uuid(sale.store_id),
        status=sale.status,
        total_due=Decimal(str(sale.total_due)),
        paid_total=Decimal(str(sale.paid_total)),
        balance_due=Decimal(str(sale.balance_due)),
        change_due=Decimal(str(sale.change_due)),
        receipt_number=sale.receipt_number,
        created_by_user_id=_normalize_uuid(sale.created_by_user_id) if sale.created_by_user_id else None,
        updated_by_user_id=_normalize_uuid(sale.updated_by_user_id) if sale.updated_by_user_id else None,
        checked_out_by_user_id=_normalize_uuid(sale.checked_out_by_user_id) if sale.checked_out_by_user_id else None,
        canceled_by_user_id=_normalize_uuid(sale.canceled_by_user_id) if sale.canceled_by_user_id else None,
        checked_out_at=sale.checked_out_at,
        canceled_at=sale.canceled_at,
        created_at=sale.created_at,
        updated_at=sale.updated_at,
    )
    return PosSaleResponse(
        header=header,
        lines=[_sale_line_response(line, returned_qty=refunded_quantities.get(_normalize_uuid(line.id), 0)) for line in lines],
        payments=[_payment_response(payment) for payment in payments],
        payment_summary=_payment_summary(payments),
        refunded_totals=refunded_totals,
        exchanged_totals=exchanged_totals,
        net_adjustment=net_adjustment,
        return_events=return_summaries,
    )


@router.get("/aris3/pos/sales", response_model=PosSaleListResponse, responses=POS_STANDARD_ERROR_RESPONSES)
def list_sales(
    receipt_number: str | None = Query(default=None),
    status: str | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    q: str | None = Query(default=None),
    sku: str | None = Query(default=None),
    epc: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    tenant_id: str | None = Query(
        default=None,
        deprecated=True,
        description="Deprecated: tenant/store scope is resolved from JWT/context.",
    ),
    token_data=Depends(get_current_token_data),
    _user=Depends(require_active_user),
    _permission=Depends(require_permission("POS_SALE_VIEW")),
    db=Depends(get_db),
):
    scoped_tenant_id = _resolve_tenant_id(token_data, token_data.tenant_id)
    store_id = None
    if token_data.store_id and token_data.role.upper() not in {role.upper() for role in DEFAULT_BROAD_STORE_ROLES}:
        store_id = token_data.store_id
    repo = PosSaleRepository(db)
    _ = tenant_id
    rows, total = repo.list_sales(
        PosSaleQueryFilters(
            tenant_id=scoped_tenant_id,
            store_id=store_id,
            receipt_number=receipt_number,
            status=status,
            from_date=_parse_filter_date(from_date),
            to_date=_parse_filter_date(to_date, end_of_day=True),
            q=q,
            sku=sku,
            epc=epc,
            page=page,
            page_size=page_size,
        )
    )
    responses = [_sale_response(repo, sale) for sale in rows]
    return PosSaleListResponse(page=page, page_size=page_size, total=total, rows=responses)


@router.post(
    "/aris3/pos/sales",
    response_model=PosSaleResponse,
    status_code=201,
    responses=POS_STANDARD_ERROR_RESPONSES,
)
def create_sale(
    request: Request,
    payload: PosSaleCreateRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    _permission=Depends(require_permission("POS_SALE_MANAGE")),
    db=Depends(get_db),
):
    _require_transaction_id(payload.transaction_id)
    scoped_tenant_id = _resolve_tenant_id(token_data, payload.tenant_id)
    enforce_tenant_scope(token_data, scoped_tenant_id, allow_superadmin=True)
    resolved_store_id = _resolve_store_id(token_data, payload.store_id)
    enforce_store_scope(token_data, resolved_store_id, db, allow_superadmin=True)

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

    if not payload.lines:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "lines must not be empty"})
    resolved_lines = [_build_sale_line_from_stock(db, tenant_id=scoped_tenant_id, line=line, store_id=resolved_store_id) for line in payload.lines]

    totals = _sale_totals(resolved_lines)
    sale = PosSale(
        tenant_id=scoped_tenant_id,
        store_id=resolved_store_id,
        status="DRAFT",
        total_due=float(totals["total_due"]),
        paid_total=float(totals["paid_total"]),
        balance_due=float(totals["balance_due"]),
        change_due=float(totals["change_due"]),
        created_by_user_id=current_user.id,
        updated_by_user_id=current_user.id,
    )
    db.add(sale)
    db.flush()

    lines = []
    for line in resolved_lines:
        snapshot = line.snapshot
        lines.append(
            PosSaleLine(
                sale_id=sale.id,
                tenant_id=scoped_tenant_id,
                line_type=line.line_type,
                qty=line.qty,
                unit_price=float(line.unit_price),
                line_total=float(_line_total(line)),
                sku=snapshot.sku,
                description=snapshot.description,
                var1_value=snapshot.var1_value,
                var2_value=snapshot.var2_value,
                epc=snapshot.epc,
                location_code=snapshot.location_code,
                pool=snapshot.pool,
                status=snapshot.status,
                location_is_vendible=snapshot.location_is_vendible,
                image_asset_id=snapshot.image_asset_id,
                image_url=snapshot.image_url,
                image_thumb_url=snapshot.image_thumb_url,
                image_source=snapshot.image_source,
                image_updated_at=snapshot.image_updated_at,
            )
        )
    db.add_all(lines)
    db.commit()

    repo = PosSaleRepository(db)
    response = _sale_response(repo, sale)
    context.record_success(status_code=201, response_body=response.model_dump(mode="json"))
    AuditService(db).record_event(
        AuditEventPayload(
            tenant_id=scoped_tenant_id,
            user_id=str(current_user.id),
            store_id=str(current_user.store_id) if current_user.store_id else None,
            trace_id=getattr(request.state, "trace_id", None),
            actor=str(current_user.username),
            action="pos_sale.create",
            entity_type="pos_sale",
            entity_id=str(sale.id),
            before=None,
            after={
                "status": sale.status,
                "total_due": str(totals["total_due"]),
                "lines": len(lines),
            },
            metadata={"transaction_id": payload.transaction_id},
            result="success",
        )
    )
    return response


@router.patch("/aris3/pos/sales/{sale_id}", response_model=PosSaleResponse, responses=POS_STANDARD_ERROR_RESPONSES)
def update_sale(
    sale_id: str,
    request: Request,
    payload: PosSaleUpdateRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    _permission=Depends(require_permission("POS_SALE_MANAGE")),
    db=Depends(get_db),
):
    _require_transaction_id(payload.transaction_id)
    scoped_tenant_id = _resolve_tenant_id(token_data, payload.tenant_id)
    enforce_tenant_scope(token_data, scoped_tenant_id, allow_superadmin=True)

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

    sale = PosSaleRepository(db).get_by_id(sale_id)
    if sale is None:
        raise AppError(ErrorCatalog.RESOURCE_NOT_FOUND, details={"message": "sale not found"})
    if str(sale.tenant_id) != scoped_tenant_id:
        raise AppError(ErrorCatalog.CROSS_TENANT_ACCESS_DENIED)
    enforce_store_scope(token_data, str(sale.store_id), db, allow_superadmin=True)
    if sale.status != "DRAFT":
        raise AppError(ErrorCatalog.BUSINESS_CONFLICT, details={"message": "sale must be DRAFT to update"})

    before = {"total_due": str(sale.total_due), "lines": len(PosSaleRepository(db).get_lines(sale_id))}
    if payload.lines is not None:
        if not payload.lines:
            raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "lines must not be empty"})
        resolved_lines = [_build_sale_line_from_stock(db, tenant_id=scoped_tenant_id, line=line, store_id=str(sale.store_id)) for line in payload.lines]
        db.execute(delete(PosSaleLine).where(PosSaleLine.sale_id == sale.id))
        lines = []
        for line in resolved_lines:
            snapshot = line.snapshot
            lines.append(
                PosSaleLine(
                    sale_id=sale.id,
                    tenant_id=scoped_tenant_id,
                    line_type=line.line_type,
                    qty=line.qty,
                    unit_price=float(line.unit_price),
                    line_total=float(_line_total(line)),
                    sku=snapshot.sku,
                    description=snapshot.description,
                    var1_value=snapshot.var1_value,
                    var2_value=snapshot.var2_value,
                    epc=snapshot.epc,
                    location_code=snapshot.location_code,
                    pool=snapshot.pool,
                    status=snapshot.status,
                    location_is_vendible=snapshot.location_is_vendible,
                    image_asset_id=snapshot.image_asset_id,
                    image_url=snapshot.image_url,
                    image_thumb_url=snapshot.image_thumb_url,
                    image_source=snapshot.image_source,
                    image_updated_at=snapshot.image_updated_at,
                )
            )
        totals = _sale_totals(resolved_lines)
        sale.total_due = float(totals["total_due"])
        sale.paid_total = float(totals["paid_total"])
        sale.balance_due = float(totals["balance_due"])
        sale.change_due = float(totals["change_due"])
        sale.updated_by_user_id = current_user.id
        sale.updated_at = datetime.utcnow()
        db.add_all(lines)
    db.commit()

    repo = PosSaleRepository(db)
    response = _sale_response(repo, sale)
    context.record_success(status_code=200, response_body=response.model_dump(mode="json"))
    AuditService(db).record_event(
        AuditEventPayload(
            tenant_id=scoped_tenant_id,
            user_id=str(current_user.id),
            store_id=str(current_user.store_id) if current_user.store_id else None,
            trace_id=getattr(request.state, "trace_id", None),
            actor=str(current_user.username),
            action="pos_sale.update",
            entity_type="pos_sale",
            entity_id=str(sale.id),
            before=before,
            after={"total_due": str(sale.total_due), "lines": len(repo.get_lines(sale_id))},
            metadata={"transaction_id": payload.transaction_id},
            result="success",
        )
    )
    return response


@router.get("/aris3/pos/sales/{sale_id}", response_model=PosSaleResponse, responses=POS_STANDARD_ERROR_RESPONSES)
def get_sale(
    sale_id: str,
    token_data=Depends(get_current_token_data),
    _user=Depends(require_active_user),
    _permission=Depends(require_permission("POS_SALE_VIEW")),
    db=Depends(get_db),
):
    sale = PosSaleRepository(db).get_by_id(sale_id)
    if sale is None:
        raise AppError(ErrorCatalog.RESOURCE_NOT_FOUND, details={"message": "sale not found"})
    scoped_tenant_id = _resolve_tenant_id(token_data, str(sale.tenant_id))
    if str(sale.tenant_id) != scoped_tenant_id:
        raise AppError(ErrorCatalog.CROSS_TENANT_ACCESS_DENIED)
    enforce_store_scope(token_data, str(sale.store_id), db, allow_superadmin=True)
    repo = PosSaleRepository(db)
    return _sale_response(repo, sale)


@router.post("/aris3/pos/sales/{sale_id}/actions", response_model=PosSaleResponse, responses=POS_STANDARD_ERROR_RESPONSES, openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "refund_only": {
                            "summary": "Refund only",
                            "value": {
                                "transaction_id": "txn-refund-only",
                                "action": "REFUND_ITEMS",
                                "receipt_number": "RCPT-1001",
                                "return_items": [{"line_id": "line-id", "qty": 1, "condition": "GOOD"}],
                                "refund_payments": [{"method": "CASH", "amount": "25.00"}],
                            },
                        },
                        "exchange_only": {
                            "summary": "Exchange only",
                            "value": {
                                "transaction_id": "txn-exchange-only",
                                "action": "EXCHANGE_ITEMS",
                                "receipt_number": "RCPT-1002",
                                "return_items": [{"line_id": "line-id", "qty": 1, "condition": "NEW"}],
                                "exchange_lines": [
                                    {
                                        "line_type": "SKU",
                                        "qty": 1,
                                        "unit_price": "25.00",
                                        "snapshot": {
                                            "sku": "SKU-NEW",
                                            "description": "Replacement",
                                            "var1_value": "V1",
                                            "var2_value": "V2",
                                            "epc": None,
                                            "location_code": "LOC-1",
                                            "pool": "P1",
                                            "status": "PENDING",
                                            "location_is_vendible": True,
                                            "image_asset_id": None,
                                            "image_url": None,
                                            "image_thumb_url": None,
                                            "image_source": None,
                                            "image_updated_at": None,
                                        },
                                    }
                                ],
                            },
                        },
                        "refund_and_exchange": {
                            "summary": "Exchange with extra refund",
                            "value": {
                                "transaction_id": "txn-refund-exchange",
                                "action": "EXCHANGE_ITEMS",
                                "receipt_number": "RCPT-1003",
                                "return_items": [{"line_id": "line-id", "qty": 1, "condition": "GOOD"}],
                                "exchange_lines": [
                                    {
                                        "line_type": "SKU",
                                        "qty": 1,
                                        "unit_price": "15.00",
                                        "snapshot": {
                                            "sku": "SKU-CHEAPER",
                                            "description": "Replacement",
                                            "var1_value": "V1",
                                            "var2_value": "V2",
                                            "epc": None,
                                            "location_code": "LOC-1",
                                            "pool": "P1",
                                            "status": "PENDING",
                                            "location_is_vendible": True,
                                            "image_asset_id": None,
                                            "image_url": None,
                                            "image_thumb_url": None,
                                            "image_source": None,
                                            "image_updated_at": None,
                                        },
                                    }
                                ],
                                "refund_payments": [{"method": "TRANSFER", "amount": "10.00"}],
                            },
                        },
                    }
                }
            }
        }
    },
)
def sale_action(
    sale_id: str,
    request: Request,
    payload: PosSaleActionRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    _permission=Depends(require_permission("POS_SALE_MANAGE")),
    db=Depends(get_db),
):
    _require_transaction_id(payload.transaction_id)
    scoped_tenant_id = _resolve_tenant_id(token_data, payload.tenant_id)
    enforce_tenant_scope(token_data, scoped_tenant_id, allow_superadmin=True)

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

    repo = PosSaleRepository(db)
    sale = repo.get_by_id(sale_id)
    if sale is None:
        raise AppError(ErrorCatalog.RESOURCE_NOT_FOUND, details={"message": "sale not found"})
    if str(sale.tenant_id) != scoped_tenant_id:
        raise AppError(ErrorCatalog.CROSS_TENANT_ACCESS_DENIED)
    enforce_store_scope(token_data, str(sale.store_id), db, allow_superadmin=True)

    if payload.action == "cancel":
        if sale.status != "DRAFT":
            raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "sale must be DRAFT to cancel"})
        sale.status = "CANCELED"
        sale.canceled_by_user_id = current_user.id
        sale.canceled_at = datetime.utcnow()
        sale.updated_by_user_id = current_user.id
        sale.updated_at = datetime.utcnow()
        db.commit()
        response = _sale_response(repo, sale)
        context.record_success(status_code=200, response_body=response.model_dump(mode="json"))
        AuditService(db).record_event(
            AuditEventPayload(
                tenant_id=scoped_tenant_id,
                user_id=str(current_user.id),
                store_id=str(current_user.store_id) if current_user.store_id else None,
                trace_id=getattr(request.state, "trace_id", None),
                actor=str(current_user.username),
                action="pos_sale.cancel",
                entity_type="pos_sale",
                entity_id=str(sale.id),
                before={"status": "DRAFT"},
                after={"status": "CANCELED"},
                metadata={"transaction_id": payload.transaction_id},
                result="success",
            )
        )
        return response

    if payload.action == "REFUND_ITEMS":
        _require_action_permission(request, token_data, db, "POS_SALE_REFUND")
        if sale.status != "PAID":
            raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "sale must be PAID to refund"})
        return_items = payload.return_items or []
        if not return_items:
            raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "return_items must not be empty"})

        policy = _get_return_policy(db, scoped_tenant_id)
        exceptions: list[str] = []
        now = datetime.utcnow()
        if policy.require_receipt and not payload.receipt_number:
            exceptions.append("receipt_required")
        if sale.checked_out_at is None:
            exceptions.append("missing_checkout_time")
        else:
            window_end = sale.checked_out_at + timedelta(days=policy.return_window_days)
            if now > window_end:
                exceptions.append("return_window_expired")

        if policy.accepted_conditions:
            for item in return_items:
                if item.condition not in policy.accepted_conditions:
                    exceptions.append("condition_not_accepted")
                    break

        refund_payments = payload.refund_payments or []
        if not refund_payments:
            raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "refund_payments must not be empty"})

        for payment in refund_payments:
            if payment.amount <= 0:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "refund payment amount must be greater than 0"},
                )
            if payment.method == "CARD" and not payment.authorization_code:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "authorization_code is required for CARD"},
                )
            if payment.method == "TRANSFER" and (not payment.bank_name or not payment.voucher_number):
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "bank_name and voucher_number are required for TRANSFER"},
                )
            if payment.method == "CASH" and not policy.allow_refund_cash:
                exceptions.append("refund_cash_not_allowed")
            if payment.method == "CARD" and not policy.allow_refund_card:
                exceptions.append("refund_card_not_allowed")
            if payment.method == "TRANSFER" and not policy.allow_refund_transfer:
                exceptions.append("refund_transfer_not_allowed")

        _require_manager_override(
            current_user,
            policy=policy,
            exceptions=exceptions,
            manager_override=payload.manager_override,
        )

        lines = repo.get_lines(sale_id)
        line_lookup = {str(line.id): line for line in lines}
        return_events = repo.get_return_events(sale_id)
        refunded_quantities = _refunded_quantities(return_events)
        subtotal = Decimal("0.00")
        returned_lines_payload: list[dict] = []
        for item in return_items:
            line = line_lookup.get(item.line_id)
            if line is None:
                raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "return line not found"})
            if item.qty < 1:
                raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "qty must be at least 1"})
            already_refunded = refunded_quantities.get(item.line_id, 0)
            if item.qty > (line.qty - already_refunded):
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "refund qty exceeds refundable balance", "line_id": item.line_id},
                )
            if line.line_type == "EPC" and item.qty != 1:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "EPC lines can only refund qty 1", "line_id": item.line_id},
                )
            unit_price = Decimal(str(line.unit_price))
            line_subtotal = (unit_price * Decimal(item.qty)).quantize(Decimal("0.01"))
            subtotal += line_subtotal
            returned_lines_payload.append(
                {
                    "line_id": item.line_id,
                    "qty": item.qty,
                    "condition": item.condition,
                    "line_type": line.line_type,
                    "sku": line.sku,
                    "epc": line.epc,
                    "unit_price": str(unit_price),
                    "line_total": str(line_subtotal),
                }
            )

        totals = _refund_totals(subtotal, Decimal(str(policy.restocking_fee_pct)))
        refund_total = totals["total"]
        refund_payment_total = sum((payment.amount for payment in refund_payments), Decimal("0.00"))
        if refund_payment_total != refund_total:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={
                    "message": "refund payments must equal refund total",
                    "refund_total": str(refund_total),
                },
            )

        cash_total = sum(
            (payment.amount for payment in refund_payments if payment.method == "CASH"),
            Decimal("0.00"),
        )
        cash_session = None
        if cash_total > 0:
            cash_session = _require_open_cash_session(
                db,
                tenant_id=scoped_tenant_id,
                store_id=str(sale.store_id),
                cashier_user_id=str(current_user.id),
            )

        before_refunded, before_exchanged, before_net, _ = _return_event_summaries(return_events)

        with db.begin_nested():
            for item in return_items:
                line = line_lookup[item.line_id]
                if line.line_type == "EPC":
                    stock_row = (
                        db.execute(
                            select(StockItem)
                            .where(
                                StockItem.tenant_id == sale.tenant_id,
                                StockItem.epc == line.epc,
                                StockItem.status == "SOLD",
                                StockItem.location_code == line.location_code,
                                StockItem.pool == line.pool,
                            )
                            .with_for_update()
                        )
                        .scalars()
                        .first()
                    )
                    if stock_row is None:
                        raise AppError(
                            ErrorCatalog.VALIDATION_ERROR,
                            details={"message": "sold stock not found for EPC refund", "epc": line.epc},
                        )
                    non_reusable = (line.status or "").upper() == "NON_REUSABLE_LABEL"
                    if non_reusable and policy.non_reusable_label_strategy == "ASSIGN_NEW_EPC":
                        stock_row.status = "PENDING"
                        stock_row.location_is_vendible = False
                        stock_row.updated_at = now
                        db.add(
                            StockItem(
                                tenant_id=sale.tenant_id,
                                store_id=sale.store_id,
                                sku=line.sku,
                                description=line.description,
                                var1_value=line.var1_value,
                                var2_value=line.var2_value,
                                epc=f"NEW-EPC-{uuid.uuid4()}" if line.epc else None,
                                location_code=line.location_code,
                                pool=line.pool,
                                status="RFID",
                                location_is_vendible=True,
                                image_asset_id=line.image_asset_id,
                                image_url=line.image_url,
                                image_thumb_url=line.image_thumb_url,
                                image_source=line.image_source,
                                image_updated_at=line.image_updated_at,
                                created_at=now,
                                updated_at=now,
                            )
                        )
                    elif non_reusable and policy.non_reusable_label_strategy == "TO_PENDING":
                        stock_row.status = "PENDING"
                        stock_row.location_is_vendible = True
                        stock_row.epc = None
                        stock_row.updated_at = now
                    else:
                        stock_row.status = "RFID"
                        stock_row.location_is_vendible = True
                        stock_row.updated_at = now
                elif line.line_type == "SKU":
                    stock_rows = (
                        db.execute(
                            select(StockItem)
                            .where(
                                StockItem.tenant_id == sale.tenant_id,
                                StockItem.sku == line.sku,
                                StockItem.status == "SOLD",
                                StockItem.location_code == line.location_code,
                                StockItem.pool == line.pool,
                            )
                            .order_by(StockItem.created_at)
                            .limit(item.qty)
                            .with_for_update()
                        )
                        .scalars()
                        .all()
                    )
                    if len(stock_rows) < item.qty:
                        raise AppError(
                            ErrorCatalog.VALIDATION_ERROR,
                            details={"message": "sold stock not found for SKU refund", "sku": line.sku},
                        )
                    for stock_row in stock_rows:
                        stock_row.status = "PENDING"
                        stock_row.location_is_vendible = True
                        stock_row.updated_at = now

            return_event = PosReturnEvent(
                tenant_id=sale.tenant_id,
                store_id=sale.store_id,
                sale_id=sale.id,
                exchange_sale_id=None,
                action="REFUND_ITEMS",
                refund_subtotal=float(totals["subtotal"]),
                restocking_fee=float(totals["restocking_fee"]),
                refund_total=float(refund_total),
                exchange_total=0.0,
                net_adjustment=float(-refund_total),
                payload={
                    "returned_lines": returned_lines_payload,
                    "refund_payments": [payment.model_dump(mode="json") for payment in refund_payments],
                    "policy_snapshot": _policy_snapshot(policy),
                    "receipt_number": payload.receipt_number,
                    "manager_override": bool(payload.manager_override),
                    "transaction_id": payload.transaction_id,
                },
                created_at=now,
            )
            db.add(return_event)
            if cash_session and cash_total > 0:
                _record_cash_movement(
                    db,
                    session=cash_session,
                    tenant_id=scoped_tenant_id,
                    store_id=str(sale.store_id),
                    sale_id=sale.id,
                    action="CASH_OUT_REFUND",
                    amount=cash_total,
                    transaction_id=payload.transaction_id,
                    actor_user_id=str(current_user.id),
                    trace_id=getattr(request.state, "trace_id", None),
                    occurred_at=now,
                )

        db.commit()
        response = _sale_response(repo, sale)
        context.record_success(status_code=200, response_body=response.model_dump(mode="json"))
        AuditService(db).record_event(
            AuditEventPayload(
                tenant_id=scoped_tenant_id,
                user_id=str(current_user.id),
                store_id=str(current_user.store_id) if current_user.store_id else None,
                trace_id=getattr(request.state, "trace_id", None),
                actor=str(current_user.username),
                action="pos_sale.refund_items",
                entity_type="pos_sale",
                entity_id=str(sale.id),
                before={
                    "refunded_totals": before_refunded.model_dump(mode="json"),
                    "exchanged_totals": before_exchanged.model_dump(mode="json"),
                    "net_adjustment": str(before_net),
                },
                after={
                    "refunded_totals": response.refunded_totals.model_dump(mode="json"),
                    "exchanged_totals": response.exchanged_totals.model_dump(mode="json"),
                    "net_adjustment": str(response.net_adjustment),
                },
                metadata={
                    "transaction_id": payload.transaction_id,
                    "policy_snapshot": _policy_snapshot(policy),
                    "returned_lines": returned_lines_payload,
                    "refund_total": str(refund_total),
                },
                result="success",
            )
        )
        return response

    if payload.action == "EXCHANGE_ITEMS":
        _require_action_permission(request, token_data, db, "POS_SALE_EXCHANGE")
        if sale.status != "PAID":
            raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "sale must be PAID to exchange"})

        return_items = payload.return_items or []
        exchange_lines = payload.exchange_lines or []
        if not return_items:
            raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "return_items must not be empty"})
        if not exchange_lines:
            raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "exchange_lines must not be empty"})
        for line in exchange_lines:
            _validate_sale_snapshot(line)

        policy = _get_return_policy(db, scoped_tenant_id)
        exceptions: list[str] = []
        now = datetime.utcnow()
        if not policy.allow_exchange:
            exceptions.append("exchange_not_allowed")
        if policy.require_receipt and not payload.receipt_number:
            exceptions.append("receipt_required")
        if sale.checked_out_at is None:
            exceptions.append("missing_checkout_time")
        else:
            window_end = sale.checked_out_at + timedelta(days=policy.return_window_days)
            if now > window_end:
                exceptions.append("return_window_expired")
        if policy.accepted_conditions:
            for item in return_items:
                if item.condition not in policy.accepted_conditions:
                    exceptions.append("condition_not_accepted")
                    break

        _require_manager_override(
            current_user,
            policy=policy,
            exceptions=exceptions,
            manager_override=payload.manager_override,
        )

        lines = repo.get_lines(sale_id)
        line_lookup = {str(line.id): line for line in lines}
        return_events = repo.get_return_events(sale_id)
        refunded_quantities = _refunded_quantities(return_events)
        subtotal = Decimal("0.00")
        returned_lines_payload: list[dict] = []
        for item in return_items:
            line = line_lookup.get(item.line_id)
            if line is None:
                raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "return line not found"})
            if item.qty < 1:
                raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "qty must be at least 1"})
            already_refunded = refunded_quantities.get(item.line_id, 0)
            if item.qty > (line.qty - already_refunded):
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "refund qty exceeds refundable balance", "line_id": item.line_id},
                )
            if line.line_type == "EPC" and item.qty != 1:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "EPC lines can only refund qty 1", "line_id": item.line_id},
                )
            unit_price = Decimal(str(line.unit_price))
            line_subtotal = (unit_price * Decimal(item.qty)).quantize(Decimal("0.01"))
            subtotal += line_subtotal
            returned_lines_payload.append(
                {
                    "line_id": item.line_id,
                    "qty": item.qty,
                    "condition": item.condition,
                    "line_type": line.line_type,
                    "sku": line.sku,
                    "epc": line.epc,
                    "unit_price": str(unit_price),
                    "line_total": str(line_subtotal),
                }
            )

        return_totals = _refund_totals(subtotal, Decimal(str(policy.restocking_fee_pct)))
        exchange_total = sum((_line_total(line) for line in exchange_lines), Decimal("0.00"))
        delta = (exchange_total - return_totals["total"]).quantize(Decimal("0.01"))

        payments = payload.payments or []
        refund_payments = payload.refund_payments or []
        cash_total = Decimal("0.00")
        if delta > 0:
            totals = _validate_payments(payments, delta)
            cash_total = totals["cash_total"]
        elif delta < 0:
            if not refund_payments:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "refund_payments required for exchange refund"},
                )
            for payment in refund_payments:
                if payment.amount <= 0:
                    raise AppError(
                        ErrorCatalog.VALIDATION_ERROR,
                        details={"message": "refund payment amount must be greater than 0"},
                    )
                if payment.method == "CARD" and not payment.authorization_code:
                    raise AppError(
                        ErrorCatalog.VALIDATION_ERROR,
                        details={"message": "authorization_code is required for CARD"},
                    )
                if payment.method == "TRANSFER" and (not payment.bank_name or not payment.voucher_number):
                    raise AppError(
                        ErrorCatalog.VALIDATION_ERROR,
                        details={"message": "bank_name and voucher_number are required for TRANSFER"},
                    )
                if payment.method == "CASH" and not policy.allow_refund_cash:
                    exceptions.append("refund_cash_not_allowed")
                if payment.method == "CARD" and not policy.allow_refund_card:
                    exceptions.append("refund_card_not_allowed")
                if payment.method == "TRANSFER" and not policy.allow_refund_transfer:
                    exceptions.append("refund_transfer_not_allowed")
            _require_manager_override(
                current_user,
                policy=policy,
                exceptions=exceptions,
                manager_override=payload.manager_override,
            )
            refund_payment_total = sum((payment.amount for payment in refund_payments), Decimal("0.00"))
            if refund_payment_total != abs(delta):
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={
                        "message": "refund payments must equal exchange refund total",
                        "refund_total": str(abs(delta)),
                    },
                )
            cash_total = sum(
                (payment.amount for payment in refund_payments if payment.method == "CASH"),
                Decimal("0.00"),
            )

        cash_session = None
        if cash_total > 0:
            cash_session = _require_open_cash_session(
                db,
                tenant_id=scoped_tenant_id,
                store_id=str(sale.store_id),
                cashier_user_id=str(current_user.id),
            )

        before_refunded, before_exchanged, before_net, _ = _return_event_summaries(return_events)

        with db.begin_nested():
            exchange_sale = PosSale(
                tenant_id=scoped_tenant_id,
                store_id=sale.store_id,
                status="PAID",
                total_due=float(exchange_total),
                paid_total=float(exchange_total),
                balance_due=0.0,
                change_due=0.0,
                created_by_user_id=current_user.id,
                updated_by_user_id=current_user.id,
                checked_out_by_user_id=current_user.id,
                checked_out_at=now,
                created_at=now,
                updated_at=now,
            )
            db.add(exchange_sale)
            db.flush()

            new_lines = []
            for line in exchange_lines:
                snapshot = line.snapshot
                new_lines.append(
                    PosSaleLine(
                        sale_id=exchange_sale.id,
                        tenant_id=scoped_tenant_id,
                        line_type=line.line_type,
                        qty=line.qty,
                        unit_price=float(line.unit_price),
                        line_total=float(_line_total(line)),
                        sku=snapshot.sku,
                        description=snapshot.description,
                        var1_value=snapshot.var1_value,
                        var2_value=snapshot.var2_value,
                        epc=snapshot.epc,
                        location_code=snapshot.location_code,
                        pool=snapshot.pool,
                        status=snapshot.status,
                        location_is_vendible=snapshot.location_is_vendible,
                        image_asset_id=snapshot.image_asset_id,
                        image_url=snapshot.image_url,
                        image_thumb_url=snapshot.image_thumb_url,
                        image_source=snapshot.image_source,
                        image_updated_at=snapshot.image_updated_at,
                        created_at=now,
                    )
                )
            db.add_all(new_lines)

            for line in exchange_lines:
                if line.line_type == "EPC":
                    stock_row = (
                        db.execute(
                            select(StockItem)
                            .where(
                                StockItem.tenant_id == sale.tenant_id,
                                StockItem.epc == line.snapshot.epc,
                                StockItem.status == "RFID",
                                StockItem.location_code == line.snapshot.location_code,
                                StockItem.pool == line.snapshot.pool,
                                StockItem.location_is_vendible.is_(True),
                            )
                            .with_for_update()
                        )
                        .scalars()
                        .first()
                    )
                    if stock_row is None:
                        raise AppError(
                            ErrorCatalog.VALIDATION_ERROR,
                            details={"message": "insufficient RFID stock for exchange EPC line", "epc": line.snapshot.epc},
                        )
                    stock_row.status = "SOLD"
                    stock_row.location_is_vendible = False
                    stock_row.updated_at = now
                elif line.line_type == "SKU":
                    stock_rows = (
                        db.execute(
                            select(StockItem)
                            .where(
                                StockItem.tenant_id == sale.tenant_id,
                                StockItem.sku == line.snapshot.sku,
                                StockItem.status == "PENDING",
                                StockItem.location_code == line.snapshot.location_code,
                                StockItem.pool == line.snapshot.pool,
                                StockItem.location_is_vendible.is_(True),
                            )
                            .order_by(StockItem.created_at)
                            .limit(line.qty)
                            .with_for_update()
                        )
                        .scalars()
                        .all()
                    )
                    if len(stock_rows) < line.qty:
                        raise AppError(
                            ErrorCatalog.VALIDATION_ERROR,
                            details={"message": "insufficient PENDING stock for exchange SKU line", "sku": line.snapshot.sku},
                        )
                    for stock_row in stock_rows:
                        stock_row.status = "SOLD"
                        stock_row.location_is_vendible = False
                        stock_row.updated_at = now

            for item in return_items:
                line = line_lookup[item.line_id]
                if line.line_type == "EPC":
                    stock_row = (
                        db.execute(
                            select(StockItem)
                            .where(
                                StockItem.tenant_id == sale.tenant_id,
                                StockItem.epc == line.epc,
                                StockItem.status == "SOLD",
                                StockItem.location_code == line.location_code,
                                StockItem.pool == line.pool,
                            )
                            .with_for_update()
                        )
                        .scalars()
                        .first()
                    )
                    if stock_row is None:
                        raise AppError(
                            ErrorCatalog.VALIDATION_ERROR,
                            details={"message": "sold stock not found for EPC return", "epc": line.epc},
                        )
                    non_reusable = (line.status or "").upper() == "NON_REUSABLE_LABEL"
                    if non_reusable and policy.non_reusable_label_strategy == "ASSIGN_NEW_EPC":
                        stock_row.status = "PENDING"
                        stock_row.location_is_vendible = False
                        stock_row.updated_at = now
                        db.add(
                            StockItem(
                                tenant_id=sale.tenant_id,
                                store_id=sale.store_id,
                                sku=line.sku,
                                description=line.description,
                                var1_value=line.var1_value,
                                var2_value=line.var2_value,
                                epc=f"NEW-EPC-{uuid.uuid4()}" if line.epc else None,
                                location_code=line.location_code,
                                pool=line.pool,
                                status="RFID",
                                location_is_vendible=True,
                                image_asset_id=line.image_asset_id,
                                image_url=line.image_url,
                                image_thumb_url=line.image_thumb_url,
                                image_source=line.image_source,
                                image_updated_at=line.image_updated_at,
                                created_at=now,
                                updated_at=now,
                            )
                        )
                    elif non_reusable and policy.non_reusable_label_strategy == "TO_PENDING":
                        stock_row.status = "PENDING"
                        stock_row.location_is_vendible = True
                        stock_row.epc = None
                        stock_row.updated_at = now
                    else:
                        stock_row.status = "RFID"
                        stock_row.location_is_vendible = True
                        stock_row.updated_at = now
                elif line.line_type == "SKU":
                    stock_rows = (
                        db.execute(
                            select(StockItem)
                            .where(
                                StockItem.tenant_id == sale.tenant_id,
                                StockItem.sku == line.sku,
                                StockItem.status == "SOLD",
                                StockItem.location_code == line.location_code,
                                StockItem.pool == line.pool,
                            )
                            .order_by(StockItem.created_at)
                            .limit(item.qty)
                            .with_for_update()
                        )
                        .scalars()
                        .all()
                    )
                    if len(stock_rows) < item.qty:
                        raise AppError(
                            ErrorCatalog.VALIDATION_ERROR,
                            details={"message": "sold stock not found for SKU return", "sku": line.sku},
                        )
                    for stock_row in stock_rows:
                        stock_row.status = "PENDING"
                        stock_row.location_is_vendible = True
                        stock_row.updated_at = now

            payment_records = []
            for payment in payments:
                payment_records.append(
                    PosPayment(
                        sale_id=exchange_sale.id,
                        tenant_id=scoped_tenant_id,
                        method=payment.method,
                        amount=float(payment.amount),
                        authorization_code=payment.authorization_code,
                        bank_name=payment.bank_name,
                        voucher_number=payment.voucher_number,
                    )
                )
            if payment_records:
                db.add_all(payment_records)

            return_event = PosReturnEvent(
                tenant_id=sale.tenant_id,
                store_id=sale.store_id,
                sale_id=sale.id,
                exchange_sale_id=exchange_sale.id,
                action="EXCHANGE_ITEMS",
                refund_subtotal=float(return_totals["subtotal"]),
                restocking_fee=float(return_totals["restocking_fee"]),
                refund_total=float(return_totals["total"]),
                exchange_total=float(exchange_total),
                net_adjustment=float(delta),
                payload={
                    "returned_lines": returned_lines_payload,
                    "exchange_lines": [line.model_dump(mode="json") for line in exchange_lines],
                    "refund_payments": [payment.model_dump(mode="json") for payment in refund_payments],
                    "collection_payments": [payment.model_dump(mode="json") for payment in payments],
                    "policy_snapshot": _policy_snapshot(policy),
                    "receipt_number": payload.receipt_number,
                    "manager_override": bool(payload.manager_override),
                    "transaction_id": payload.transaction_id,
                    "exchange_sale_id": str(exchange_sale.id),
                },
                created_at=now,
            )
            db.add(return_event)

            if cash_session and cash_total > 0:
                _record_cash_movement(
                    db,
                    session=cash_session,
                    tenant_id=scoped_tenant_id,
                    store_id=str(sale.store_id),
                    sale_id=sale.id,
                    action="CASH_OUT_REFUND" if delta < 0 else "SALE",
                    amount=cash_total,
                    transaction_id=payload.transaction_id,
                    actor_user_id=str(current_user.id),
                    trace_id=getattr(request.state, "trace_id", None),
                    occurred_at=now,
                )

        response = _sale_response(repo, sale)
        context.record_success(status_code=200, response_body=response.model_dump(mode="json"))
        AuditService(db).record_event(
            AuditEventPayload(
                tenant_id=scoped_tenant_id,
                user_id=str(current_user.id),
                store_id=str(current_user.store_id) if current_user.store_id else None,
                trace_id=getattr(request.state, "trace_id", None),
                actor=str(current_user.username),
                action="pos_sale.exchange_items",
                entity_type="pos_sale",
                entity_id=str(sale.id),
                before={
                    "refunded_totals": before_refunded.model_dump(mode="json"),
                    "exchanged_totals": before_exchanged.model_dump(mode="json"),
                    "net_adjustment": str(before_net),
                },
                after={
                    "refunded_totals": response.refunded_totals.model_dump(mode="json"),
                    "exchanged_totals": response.exchanged_totals.model_dump(mode="json"),
                    "net_adjustment": str(response.net_adjustment),
                },
                metadata={
                    "transaction_id": payload.transaction_id,
                    "policy_snapshot": _policy_snapshot(policy),
                    "returned_lines": returned_lines_payload,
                    "exchange_total": str(exchange_total),
                    "delta": str(delta),
                },
                result="success",
            )
        )
        return response

    if payload.action != "checkout":
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "unsupported action"})
    if sale.status != "DRAFT":
        raise AppError(ErrorCatalog.BUSINESS_CONFLICT, details={"message": "sale must be DRAFT to checkout"})

    lines = repo.get_lines(sale_id)
    if not lines:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "sale has no lines"})

    total_due = sum((Decimal(str(line.line_total)) for line in lines), Decimal("0.00"))
    payments = payload.payments or []
    totals = _validate_payments(payments, total_due)

    cash_session = None
    if totals["cash_total"] > 0:
        cash_session = _require_open_cash_session(
            db,
            tenant_id=scoped_tenant_id,
            store_id=str(sale.store_id),
            cashier_user_id=str(current_user.id),
        )

    now = datetime.utcnow()
    for line in lines:
        if line.line_type == "EPC":
            stock_row = (
                db.execute(
                    select(StockItem)
                    .where(
                        StockItem.tenant_id == sale.tenant_id,
                        StockItem.epc == line.epc,
                        StockItem.status == "RFID",
                        StockItem.location_code == line.location_code,
                        StockItem.pool == line.pool,
                        StockItem.location_is_vendible.is_(True),
                    )
                    .with_for_update()
                )
                .scalars()
                .first()
            )
            if stock_row is None:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "insufficient RFID stock for EPC line", "epc": line.epc},
                )
            stock_row.status = "SOLD"
            stock_row.location_is_vendible = False
            stock_row.updated_at = now
        elif line.line_type == "SKU":
            stock_rows = (
                db.execute(
                    select(StockItem)
                    .where(
                        StockItem.tenant_id == sale.tenant_id,
                        StockItem.sku == line.sku,
                        StockItem.status == "PENDING",
                        StockItem.location_code == line.location_code,
                        StockItem.pool == line.pool,
                        StockItem.location_is_vendible.is_(True),
                    )
                    .order_by(StockItem.created_at)
                    .limit(line.qty)
                    .with_for_update()
                )
                .scalars()
                .all()
            )
            if len(stock_rows) < line.qty:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "insufficient PENDING stock for SKU line", "sku": line.sku},
                )
            for stock_row in stock_rows:
                stock_row.status = "SOLD"
                stock_row.location_is_vendible = False
                stock_row.updated_at = now

    sale.status = "PAID"
    sale.total_due = float(totals["total_due"])
    sale.paid_total = float(totals["paid_total"])
    sale.balance_due = float(totals["balance_due"])
    sale.change_due = float(totals["change_due"])
    sale.checked_out_by_user_id = current_user.id
    sale.checked_out_at = now
    sale.receipt_number = payload.receipt_number or sale.receipt_number
    sale.updated_by_user_id = current_user.id
    sale.updated_at = now

    payment_records = []
    for payment in payments:
        payment_records.append(
            PosPayment(
                sale_id=sale.id,
                tenant_id=scoped_tenant_id,
                method=payment.method,
                amount=float(payment.amount),
                authorization_code=payment.authorization_code,
                bank_name=payment.bank_name,
                voucher_number=payment.voucher_number,
            )
        )
    if payment_records:
        db.add_all(payment_records)

    if cash_session:
        _record_cash_movement(
            db,
            session=cash_session,
            tenant_id=scoped_tenant_id,
            store_id=str(sale.store_id),
            sale_id=sale.id,
            action="SALE",
            amount=totals["cash_total"],
            transaction_id=payload.transaction_id,
            actor_user_id=str(current_user.id),
            trace_id=getattr(request.state, "trace_id", None),
            occurred_at=now,
        )
    db.commit()

    response = _sale_response(repo, sale)
    context.record_success(status_code=200, response_body=response.model_dump(mode="json"))
    AuditService(db).record_event(
        AuditEventPayload(
            tenant_id=scoped_tenant_id,
            user_id=str(current_user.id),
            store_id=str(current_user.store_id) if current_user.store_id else None,
            trace_id=getattr(request.state, "trace_id", None),
            actor=str(current_user.username),
            action="pos_sale.checkout",
            entity_type="pos_sale",
            entity_id=str(sale.id),
            before={"status": "DRAFT", "total_due": str(total_due)},
            after={
                "status": "PAID",
                "total_due": str(totals["total_due"]),
                "paid_total": str(totals["paid_total"]),
                "change_due": str(totals["change_due"]),
            },
            metadata={
                "transaction_id": payload.transaction_id,
                "payment_summary": [
                    {"method": p.method, "amount": str(p.amount)} for p in payments
                ],
            },
            result="success",
        )
    )
    return response
