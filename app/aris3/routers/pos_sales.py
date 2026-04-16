from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
import logging
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
    EpcAssignment,
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
    SaleSummaryRow,
)
from app.aris3.services.access_control import AccessControlService
from app.aris3.services.audit import AuditEventPayload, AuditService
from app.aris3.services.idempotency import IdempotencyService, extract_idempotency_key
from app.aris3.services.stock_rules import sale_epc_filters, sale_sku_filters


router = APIRouter()
logger = logging.getLogger(__name__)
POS_RETURN_AGGREGATE_ACTIONS = {"REFUND_ITEMS", "EXCHANGE_ITEMS"}


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


POS_ERROR_EXAMPLES = {
    "401": {"code": "UNAUTHORIZED", "message": "Authentication required", "details": {"message": "Missing or invalid bearer token"}, "trace_id": "trace-auth-401"},
    "403": {"code": "FORBIDDEN", "message": "You do not have access to this store", "details": {"store_id": "00000000-0000-0000-0000-000000000099", "required_permission": "POS_SALE_MANAGE"}, "trace_id": "trace-authz-403"},
    "404_sale": {"code": "NOT_FOUND", "message": "sale not found", "details": {"sale_id": "00000000-0000-0000-0000-000000009999"}, "trace_id": "trace-sale-404"},
    "409_draft_required": {"code": "BUSINESS_CONFLICT", "message": "sale must be DRAFT to update", "details": {"sale_id": "00000000-0000-0000-0000-000000000111", "status": "PAID"}, "trace_id": "trace-sale-409"},
    "409_idempotency": {"code": "BUSINESS_CONFLICT", "message": "Idempotency conflict: transaction_id already used with different payload", "details": {"transaction_id": "txn-checkout-1001"}, "trace_id": "trace-sale-idempotency-409"},
}

_IDEMPOTENCY_REQUIRED_HEADER_PARAMETER = {
    "name": "Idempotency-Key",
    "in": "header",
    "required": True,
    "schema": {"type": "string"},
    "description": "Idempotency key required for mutation safety. Legacy alias X-Idempotency-Key is also accepted.",
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


def _legacy_unit_price(line: PosSaleLineCreate):
    return line.__dict__.get("unit_price")


def _legacy_snapshot(line: PosSaleLineCreate):
    return line.__dict__.get("snapshot")


def _line_fallback_price(line: PosSaleLineCreate) -> Decimal:
    unit_price = _legacy_unit_price(line)
    if unit_price is not None:
        return Decimal(str(unit_price)).quantize(Decimal("0.01"))
    return Decimal("0.00")


def _line_snapshot_or_default(line: PosSaleLineCreate) -> PosSaleLineSnapshot:
    snapshot = _legacy_snapshot(line)
    if snapshot is not None:
        return snapshot
    return PosSaleLineSnapshot(
        sku=line.sku,
        epc=line.__dict__.get("epc") if line.line_type == "EPC" else None,
        location_is_vendible=True,
    )


def _build_sale_line_from_stock(db, *, tenant_id: str, line: PosSaleLineCreate, store_id: str) -> PosSaleLineCreate:
    _validate_sale_snapshot(line)
    snapshot = _line_snapshot_or_default(line)
    fallback_price = _line_fallback_price(line)

    if line.line_type == "EPC":
        epc = snapshot.epc or line.epc
        filters = list(sale_epc_filters(tenant_id=tenant_id, store_id=store_id, epc=epc))
        if snapshot.location_code:
            filters.append(StockItem.location_code == snapshot.location_code)
        if snapshot.pool:
            filters.append(StockItem.pool == snapshot.pool)
        stock = db.execute(select(StockItem).where(*filters)).scalars().first()
        if not stock:
            raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "epc not available for sale", "epc": epc})

        expected_price = _authoritative_price(stock, fallback_price)
        if _legacy_unit_price(line) is not None and fallback_price != expected_price and stock.sale_price is not None:
            raise AppError(ErrorCatalog.BUSINESS_CONFLICT, details={"message": "unit_price mismatch", "expected": str(expected_price), "received": str(fallback_price)})

        rebuilt_snapshot = PosSaleLineSnapshot(
            item_uid=stock.item_uid,
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

    sku = snapshot.sku or line.sku
    filters = list(sale_sku_filters(tenant_id=tenant_id, store_id=store_id, sku=sku))
    if snapshot.location_code:
        filters.append(StockItem.location_code == snapshot.location_code)
    if snapshot.pool:
        filters.append(StockItem.pool == snapshot.pool)

    count = db.execute(select(func.count()).select_from(StockItem).where(*filters)).scalar_one()
    if int(count or 0) < line.qty:
        if _legacy_unit_price(line) is not None:
            return PosSaleLineCreate(
                line_type=line.line_type,
                qty=line.qty,
                unit_price=fallback_price,
                snapshot=PosSaleLineSnapshot(
                    sku=sku,
                    description=snapshot.description,
                    var1_value=snapshot.var1_value,
                    var2_value=snapshot.var2_value,
                    epc=None,
                    location_code=snapshot.location_code,
                    pool=snapshot.pool,
                    status=snapshot.status or "PENDING",
                    location_is_vendible=True,
                ),
            )
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "insufficient stock for sku", "sku": sku})

    stock = db.execute(select(StockItem).where(*filters).order_by(StockItem.created_at)).scalars().first()
    if not stock:
        if _legacy_unit_price(line) is not None:
            return PosSaleLineCreate(
                line_type=line.line_type,
                qty=line.qty,
                unit_price=fallback_price,
                snapshot=PosSaleLineSnapshot(
                    sku=sku,
                    description=snapshot.description,
                    var1_value=snapshot.var1_value,
                    var2_value=snapshot.var2_value,
                    epc=None,
                    location_code=snapshot.location_code,
                    pool=snapshot.pool,
                    status=snapshot.status or "PENDING",
                    location_is_vendible=True,
                ),
            )
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "sku not available for sale", "sku": sku})

    expected_price = _authoritative_price(stock, fallback_price)
    # Transitional backward compatibility: accept legacy unit_price as fallback when catalog/stock has no sale_price.
    if _legacy_unit_price(line) is not None and fallback_price != expected_price and stock.sale_price is not None:
        raise AppError(ErrorCatalog.BUSINESS_CONFLICT, details={"message": "unit_price mismatch", "expected": str(expected_price), "received": str(fallback_price), "sku": sku})

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
    snapshot = _line_snapshot_or_default(line)
    if line.qty < 1:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "qty must be at least 1", "qty": line.qty},
        )
    if _legacy_unit_price(line) is not None and _legacy_unit_price(line) < 0:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "unit_price must be >= 0", "unit_price": str(_legacy_unit_price(line))},
        )
    if line.line_type == "EPC":
        if line.qty != 1:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "qty must be 1 for EPC lines", "qty": line.qty},
            )
        if not (snapshot.epc or line.epc):
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "epc is required for EPC lines"},
            )
    if line.line_type == "SKU":
        if snapshot.epc is not None:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "epc must be empty for SKU lines"},
            )
        if not (snapshot.sku or line.sku):
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "sku is required for SKU lines"},
            )
def _line_total(line: PosSaleLineCreate) -> Decimal:
    return (Decimal(str(_legacy_unit_price(line) or 0)) * Decimal(line.qty)).quantize(Decimal("0.01"))


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
        if event.action not in POS_RETURN_AGGREGATE_ACTIONS:
            continue
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
        if event.action not in POS_RETURN_AGGREGATE_ACTIONS:
            continue
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


def _require_open_cash_session(
    db,
    *,
    tenant_id: str,
    store_id: str,
    cashier_user_id: str,
    trace_id: str | None = None,
    sale_id: str | None = None,
) -> PosCashSession:
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
    if session is not None:
        logger.info(
            "pos.cash_session.resolve.ok tenant_id=%s store_id=%s cashier_user_id=%s cash_session_id=%s sale_id=%s trace_id=%s register_id=%s terminal_id=%s",
            tenant_id,
            store_id,
            cashier_user_id,
            str(session.id),
            sale_id,
            trace_id,
            None,
            None,
        )
        return session
    fallback_sessions = (
        db.execute(
            select(PosCashSession).where(
                PosCashSession.tenant_id == tenant_id,
                PosCashSession.store_id == store_id,
                PosCashSession.status == "OPEN",
            )
        )
        .scalars()
        .all()
    )
    if len(fallback_sessions) == 1:
        fallback = fallback_sessions[0]
        logger.warning(
            "pos.cash_session.resolve.fallback tenant_id=%s store_id=%s requested_cashier_user_id=%s session_cashier_user_id=%s cash_session_id=%s sale_id=%s trace_id=%s register_id=%s terminal_id=%s",
            tenant_id,
            store_id,
            cashier_user_id,
            str(fallback.cashier_user_id),
            str(fallback.id),
            sale_id,
            trace_id,
            None,
            None,
        )
        return fallback
    logger.warning(
        "pos.cash_session.resolve.missing tenant_id=%s store_id=%s cashier_user_id=%s open_sessions=%s sale_id=%s trace_id=%s register_id=%s terminal_id=%s",
        tenant_id,
        store_id,
        cashier_user_id,
        len(fallback_sessions),
        sale_id,
        trace_id,
        None,
        None,
    )
    if session is None:
        raise AppError(
            ErrorCatalog.BUSINESS_CONFLICT,
            details={"message": "open cash session required for CASH payments"},
        )
    return session


def _sale_line_response(line: PosSaleLine, *, returned_qty: int = 0) -> PosSaleLineResponse:
    snapshot = PosSaleLineSnapshot(
        item_uid=line.item_uid,
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


def _sale_summary_row(repo: PosSaleRepository, sale: PosSale) -> SaleSummaryRow:
    lines = repo.get_lines(str(sale.id))
    payments = repo.get_payments(str(sale.id))
    return SaleSummaryRow(
        id=_normalize_uuid(sale.id),
        receipt_number=sale.receipt_number,
        store_id=_normalize_uuid(sale.store_id),
        status=sale.status,
        business_date=getattr(sale, "business_date", None),
        timezone=getattr(sale, "timezone", None),
        total_due=Decimal(str(sale.total_due)),
        paid_total=Decimal(str(sale.paid_total)),
        balance_due=Decimal(str(sale.balance_due)),
        item_count=sum(int(line.qty or 0) for line in lines),
        payment_summary=_payment_summary(payments),
        checked_out_at=sale.checked_out_at,
        created_at=sale.created_at,
    )


@router.get(
    "/aris3/pos/sales",
    response_model=PosSaleListResponse,
    responses=POS_LIST_ERROR_RESPONSES,
    openapi_extra={
        "responses": {
            "401": {"content": {"application/json": {"example": POS_ERROR_EXAMPLES["401"]}}},
            "403": {"content": {"application/json": {"example": POS_ERROR_EXAMPLES["403"]}}},
            "409": {"content": {"application/json": {"example": POS_ERROR_EXAMPLES["409_idempotency"]}}},
            "422": {"content": {"application/json": {"example": {"code": "VALIDATION_ERROR", "message": "Validation error", "details": {"errors": [{"field": "checked_out_from", "message": "checked_out_from must be <= checked_out_to", "type": "value_error"}]}, "trace_id": "trace-sales-list-422"}}}},
        }
    },
)
def list_sales(
    receipt_number: str | None = Query(default=None),
    status: str | None = Query(default=None),
    checked_out_from: date | None = Query(default=None, description="Inclusive calendar date (store business date) to start filtering sales by checkout date."),
    checked_out_to: date | None = Query(default=None, description="Inclusive calendar date (store business date) to end filtering sales by checkout date."),
    q: str | None = Query(default=None),
    sku: str | None = Query(default=None),
    epc: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
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
    rows, total = repo.list_sales(
        PosSaleQueryFilters(
            tenant_id=scoped_tenant_id,
            store_id=store_id,
            receipt_number=receipt_number,
            status=status,
            from_date=_parse_filter_date(checked_out_from),
            to_date=_parse_filter_date(checked_out_to, end_of_day=True),
            q=q,
            sku=sku,
            epc=epc,
            page=page,
            page_size=page_size,
        )
    )
    responses = [_sale_summary_row(repo, sale) for sale in rows]
    return PosSaleListResponse(page=page, page_size=page_size, total=total, rows=responses)


@router.post(
    "/aris3/pos/sales",
    response_model=PosSaleResponse,
    status_code=201,
    responses=POS_STANDARD_ERROR_RESPONSES,
    summary="Create draft sale",
    description="Creates a sale in DRAFT status using canonical line selectors (`line_type` + `sku`/`epc`).",
    openapi_extra={
        "parameters": [_IDEMPOTENCY_REQUIRED_HEADER_PARAMETER],
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "canonical": {
                            "summary": "Canonical draft sale request",
                            "value": {
                                "transaction_id": "txn-sale-create-1001",
                                "store_id": "00000000-0000-0000-0000-000000000001",
                                "lines": [
                                    {"line_type": "SKU", "sku": "SKU-123", "qty": 2},
                                    {"line_type": "EPC", "epc": "EPC-0001", "qty": 1}
                                ]
                            }
                        }
                    }
                }
            }
        },
        "responses": {
            "201": {"content": {"application/json": {"example": {"header": {"id": "00000000-0000-0000-0000-000000000111", "tenant_id": "00000000-0000-0000-0000-000000000010", "store_id": "00000000-0000-0000-0000-000000000001", "status": "DRAFT", "total_due": "50.00", "paid_total": "0.00", "balance_due": "50.00", "change_due": "0.00", "receipt_number": None, "created_by_user_id": "00000000-0000-0000-0000-000000000020", "updated_by_user_id": "00000000-0000-0000-0000-000000000020", "checked_out_by_user_id": None, "canceled_by_user_id": None, "checked_out_at": None, "canceled_at": None, "created_at": "2026-01-15T10:00:00Z", "updated_at": "2026-01-15T10:00:00Z"}, "lines": [{"id": "00000000-0000-0000-0000-000000001001", "line_type": "SKU", "qty": 2, "unit_price": "25.00", "line_total": "50.00", "returned_qty": 0, "returnable_qty": 2, "snapshot": {"sku": "SKU-123", "epc": None}, "created_at": "2026-01-15T10:00:00Z"}], "payments": [], "payment_summary": [], "refunded_totals": {"subtotal": "0.00", "restocking_fee": "0.00", "total": "0.00"}, "exchanged_totals": {"subtotal": "0.00", "restocking_fee": "0.00", "total": "0.00"}, "net_adjustment": "0.00", "return_events": []}}}},
            "401": {"content": {"application/json": {"example": POS_ERROR_EXAMPLES["401"]}}},
            "403": {"content": {"application/json": {"example": POS_ERROR_EXAMPLES["403"]}}},
            "404": {"content": {"application/json": {"example": POS_ERROR_EXAMPLES["404_sale"]}}},
            "409": {"content": {"application/json": {"examples": {"draft_state_conflict": {"value": POS_ERROR_EXAMPLES["409_draft_required"]}, "idempotency_conflict": {"value": POS_ERROR_EXAMPLES["409_idempotency"]}}}}},
            "422": {"content": {"application/json": {"example": {"code": "VALIDATION_ERROR", "message": "Validation error", "details": {"errors": [{"field": "lines[0].sku", "message": "sku is required for SKU lines", "type": "value_error", "loc": ["body", "lines", 0, "sku"]}]}, "trace_id": "trace-sale-create-422"}}}},
        },
    },
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
    scoped_tenant_id = _resolve_tenant_id(token_data, token_data.tenant_id)
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
        sale_code=f"SALE-{uuid.uuid4().hex[:12].upper()}",
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
        snapshot = _legacy_snapshot(line)
        lines.append(
            PosSaleLine(
                sale_line_id=f"SL-{uuid.uuid4().hex[:12].upper()}",
                sale_id=sale.id,
                tenant_id=scoped_tenant_id,
                line_type=line.line_type,
                qty=line.qty,
                unit_price=float(_legacy_unit_price(line) or Decimal("0.00")),
                line_total=float(_line_total(line)),
                sku=snapshot.sku,
                description=snapshot.description,
                var1_value=snapshot.var1_value,
                var2_value=snapshot.var2_value,
                epc=snapshot.epc,
                item_uid=getattr(snapshot, "item_uid", None),
                sku_snapshot=snapshot.sku,
                description_snapshot=snapshot.description,
                var1_snapshot=snapshot.var1_value,
                var2_snapshot=snapshot.var2_value,
                sale_price_snapshot=_legacy_unit_price(line) or Decimal("0.00"),
                epc_at_sale=snapshot.epc,
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
            store_id=resolved_store_id,
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


@router.patch(
    "/aris3/pos/sales/{sale_id}",
    response_model=PosSaleResponse,
    responses=POS_STANDARD_ERROR_RESPONSES,
    summary="Replace draft sale lines",
    description="Allowed only when the sale is in DRAFT status. This PATCH performs a full replacement of draft lines (`lines` array), preserving identifier and draft lifecycle; this is not an arbitrary partial patch.",
    openapi_extra={
        "parameters": [_IDEMPOTENCY_REQUIRED_HEADER_PARAMETER],
        "requestBody": {
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/PosSaleUpdateRequest"},
                    "examples": {
                        "replace_draft_lines": {
                            "summary": "Replace all draft lines using canonical selectors",
                            "value": {
                                "transaction_id": "txn-sale-update-1002",
                                "lines": [
                                    {"line_type": "SKU", "sku": "SKU-123", "qty": 1},
                                    {"line_type": "EPC", "epc": "EPC-0002", "qty": 1}
                                ],
                            },
                        }
                    },
                }
            }
        },
        "responses": {
            "200": {"content": {"application/json": {"example": {"header": {"id": "00000000-0000-0000-0000-000000000111", "status": "DRAFT", "checked_out_at": None, "canceled_at": None, "total_due": "25.00", "paid_total": "0.00", "balance_due": "25.00", "change_due": "0.00", "tenant_id": "00000000-0000-0000-0000-000000000010", "store_id": "00000000-0000-0000-0000-000000000001", "created_at": "2026-01-15T10:00:00Z", "updated_at": "2026-01-15T10:15:00Z", "receipt_number": None, "created_by_user_id": "00000000-0000-0000-0000-000000000020", "updated_by_user_id": "00000000-0000-0000-0000-000000000020", "checked_out_by_user_id": None, "canceled_by_user_id": None}, "lines": [{"id": "00000000-0000-0000-0000-000000001002", "line_type": "SKU", "sku": "SKU-456", "qty": 1, "unit_price": "25.00", "line_total": "25.00", "returned_qty": 0, "returnable_qty": 1, "snapshot": {"sku": "SKU-456"}, "created_at": "2026-01-15T10:15:00Z"}], "payments": [], "payment_summary": [], "refunded_totals": {"subtotal": "0.00", "restocking_fee": "0.00", "total": "0.00"}, "exchanged_totals": {"subtotal": "0.00", "restocking_fee": "0.00", "total": "0.00"}, "net_adjustment": "0.00", "return_events": []}}}},
            "401": {"content": {"application/json": {"example": POS_ERROR_EXAMPLES["401"]}}},
            "403": {"content": {"application/json": {"example": POS_ERROR_EXAMPLES["403"]}}},
            "404": {"content": {"application/json": {"example": POS_ERROR_EXAMPLES["404_sale"]}}},
            "409": {"content": {"application/json": {"example": POS_ERROR_EXAMPLES["409_draft_required"]}}},
            "422": {"content": {"application/json": {"example": {"code": "VALIDATION_ERROR", "message": "Validation error", "details": {"errors": [{"field": "lines", "message": "lines must not be empty", "type": "value_error"}]}, "trace_id": "trace-sale-patch-422"}}}},
        }
    },
)
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
    scoped_tenant_id = _resolve_tenant_id(token_data, token_data.tenant_id)
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
            snapshot = _legacy_snapshot(line)
            lines.append(
                PosSaleLine(
                    sale_id=sale.id,
                    tenant_id=scoped_tenant_id,
                    sale_line_id=f"SL-{uuid.uuid4().hex[:12].upper()}",
                    line_type=line.line_type,
                    qty=line.qty,
                    unit_price=float(_legacy_unit_price(line) or Decimal("0.00")),
                    line_total=float(_line_total(line)),
                    sku=snapshot.sku,
                    description=snapshot.description,
                    var1_value=snapshot.var1_value,
                    var2_value=snapshot.var2_value,
                    epc=snapshot.epc,
                    item_uid=getattr(snapshot, "item_uid", None),
                    sku_snapshot=snapshot.sku,
                    description_snapshot=snapshot.description,
                    var1_snapshot=snapshot.var1_value,
                    var2_snapshot=snapshot.var2_value,
                    sale_price_snapshot=_legacy_unit_price(line) or Decimal("0.00"),
                    epc_at_sale=snapshot.epc,
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
            store_id=str(sale.store_id),
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


@router.get(
    "/aris3/pos/sales/{sale_id}",
    response_model=PosSaleResponse,
    responses=POS_STANDARD_ERROR_RESPONSES,
    openapi_extra={
        "responses": {
            "200": {"content": {"application/json": {"example": {"header": {"id": "00000000-0000-0000-0000-000000000111", "status": "PAID", "checked_out_at": "2026-01-15T11:00:00Z", "canceled_at": None, "total_due": "50.00", "paid_total": "50.00", "balance_due": "0.00", "change_due": "0.00", "tenant_id": "00000000-0000-0000-0000-000000000010", "store_id": "00000000-0000-0000-0000-000000000001", "created_at": "2026-01-15T10:00:00Z", "updated_at": "2026-01-15T11:00:00Z", "receipt_number": "RCPT-1001", "created_by_user_id": "00000000-0000-0000-0000-000000000020", "updated_by_user_id": "00000000-0000-0000-0000-000000000020", "checked_out_by_user_id": "00000000-0000-0000-0000-000000000020", "canceled_by_user_id": None}, "lines": [], "payments": [{"id": "00000000-0000-0000-0000-000000008001", "method": "CASH", "amount": "50.00", "authorization_code": None, "bank_name": None, "voucher_number": None, "created_at": "2026-01-15T11:00:00Z"}], "payment_summary": [{"method": "CASH", "amount": "50.00"}], "refunded_totals": {"subtotal": "0.00", "restocking_fee": "0.00", "total": "0.00"}, "exchanged_totals": {"subtotal": "0.00", "restocking_fee": "0.00", "total": "0.00"}, "net_adjustment": "0.00", "return_events": []}}}},
            "401": {"content": {"application/json": {"example": POS_ERROR_EXAMPLES["401"]}}},
            "403": {"content": {"application/json": {"example": POS_ERROR_EXAMPLES["403"]}}},
            "404": {"content": {"application/json": {"example": POS_ERROR_EXAMPLES["404_sale"]}}},
            "409": {"content": {"application/json": {"example": POS_ERROR_EXAMPLES["409_idempotency"]}}},
            "422": {"content": {"application/json": {"example": {"code": "VALIDATION_ERROR", "message": "Validation error", "details": {"errors": [{"field": "sale_id", "message": "sale_id must be a valid UUID", "type": "type_error.uuid"}]}, "trace_id": "trace-sale-get-422"}}}},
        }
    },
)
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


@router.post("/aris3/pos/sales/{sale_id}/actions", response_model=PosSaleResponse, responses=POS_STANDARD_ERROR_RESPONSES,
    summary="Execute sale action",
    description=(
        "Canonical POS flow uses `/aris3/pos/returns` for refunds/exchanges. "
        "`REFUND_ITEMS` and `EXCHANGE_ITEMS` are maintained as compatibility wrappers on sales actions. "
        "Legacy lowercase is accepted and normalized."
    ),
    openapi_extra={
        "parameters": [_IDEMPOTENCY_REQUIRED_HEADER_PARAMETER],
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "checkout": {
                            "summary": "Checkout sale",
                            "value": {"transaction_id": "txn-checkout-1001", "action": "CHECKOUT", "payments": [{"method": "CASH", "amount": "25.00"}]},
                        },
                        "cancel": {
                            "summary": "Cancel draft sale",
                            "value": {"transaction_id": "txn-cancel-1002", "action": "CANCEL"},
                        },
                    },
                }
            }
        },
        "responses": {
            "200": {"content": {"application/json": {"examples": {"checkout": {"value": {"header": {"id": "00000000-0000-0000-0000-000000000111", "status": "PAID", "checked_out_at": "2026-01-15T11:00:00Z", "canceled_at": None, "tenant_id": "00000000-0000-0000-0000-000000000010", "store_id": "00000000-0000-0000-0000-000000000001", "total_due": "50.00", "paid_total": "50.00", "balance_due": "0.00", "change_due": "0.00", "receipt_number": "RCPT-1001", "created_by_user_id": "00000000-0000-0000-0000-000000000020", "updated_by_user_id": "00000000-0000-0000-0000-000000000020", "checked_out_by_user_id": "00000000-0000-0000-0000-000000000020", "canceled_by_user_id": None, "created_at": "2026-01-15T10:00:00Z", "updated_at": "2026-01-15T11:00:00Z"}, "lines": [], "payments": [{"id": "00000000-0000-0000-0000-000000008001", "method": "CASH", "amount": "50.00", "authorization_code": None, "bank_name": None, "voucher_number": None, "created_at": "2026-01-15T11:00:00Z"}], "payment_summary": [{"method": "CASH", "amount": "50.00"}], "refunded_totals": {"subtotal": "0.00", "restocking_fee": "0.00", "total": "0.00"}, "exchanged_totals": {"subtotal": "0.00", "restocking_fee": "0.00", "total": "0.00"}, "net_adjustment": "0.00", "return_events": []}}, "cancel": {"value": {"header": {"id": "00000000-0000-0000-0000-000000000112", "status": "CANCELED", "checked_out_at": None, "canceled_at": "2026-01-15T11:05:00Z", "tenant_id": "00000000-0000-0000-0000-000000000010", "store_id": "00000000-0000-0000-0000-000000000001", "total_due": "25.00", "paid_total": "0.00", "balance_due": "25.00", "change_due": "0.00", "receipt_number": None, "created_by_user_id": "00000000-0000-0000-0000-000000000020", "updated_by_user_id": "00000000-0000-0000-0000-000000000020", "checked_out_by_user_id": None, "canceled_by_user_id": "00000000-0000-0000-0000-000000000020", "created_at": "2026-01-15T10:00:00Z", "updated_at": "2026-01-15T11:05:00Z"}, "lines": [], "payments": [], "payment_summary": [], "refunded_totals": {"subtotal": "0.00", "restocking_fee": "0.00", "total": "0.00"}, "exchanged_totals": {"subtotal": "0.00", "restocking_fee": "0.00", "total": "0.00"}, "net_adjustment": "0.00", "return_events": []}}}}}},
            "401": {"content": {"application/json": {"example": POS_ERROR_EXAMPLES["401"]}}},
            "403": {"content": {"application/json": {"example": POS_ERROR_EXAMPLES["403"]}}},
            "404": {"content": {"application/json": {"example": POS_ERROR_EXAMPLES["404_sale"]}}},
            "409": {"content": {"application/json": {"example": POS_ERROR_EXAMPLES["409_draft_required"]}}},
            "422": {"content": {"application/json": {"example": {"code": "VALIDATION_ERROR", "message": "Validation error", "details": {"errors": [{"field": "payments", "message": "payments are required for CHECKOUT action", "type": "value_error"}]}, "trace_id": "trace-sale-action-422"}}}},
        },
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
    scoped_tenant_id = _resolve_tenant_id(token_data, token_data.tenant_id)
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

    action = str(payload.action).upper()
    effective_store_id = str(sale.store_id)

    if action == "CANCEL":
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
                store_id=effective_store_id,
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

    if action == "REFUND_ITEMS":
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
                                StockItem.store_id == sale.store_id,
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
                                StockItem.store_id == sale.store_id,
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
                store_id=effective_store_id,
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

    if action == "EXCHANGE_ITEMS":
        _require_action_permission(request, token_data, db, "POS_SALE_EXCHANGE")
        if sale.status != "PAID":
            raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "sale must be PAID to exchange"})

        return_items = payload.return_items or []
        exchange_lines = payload.exchange_lines or []
        if not return_items:
            raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "return_items must not be empty"})
        if not exchange_lines:
            raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "exchange_lines must not be empty"})
        resolved_exchange_lines = [
            _build_sale_line_from_stock(db, tenant_id=scoped_tenant_id, line=line, store_id=str(sale.store_id))
            for line in exchange_lines
        ]

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
        exchange_total = sum((_line_total(line) for line in resolved_exchange_lines), Decimal("0.00"))
        delta = (exchange_total - return_totals["total"]).quantize(Decimal("0.01"))

        payments = payload.payments or []
        refund_payments = payload.refund_payments or []
        cash_total = Decimal("0.00")
        if delta > 0:
            if not payments:
                raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "payments required for exchange collection"})
            if refund_payments:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "refund_payments are not allowed when exchange delta is positive"},
                )
            totals = _validate_payments(payments, delta)
            cash_total = totals["cash_total"]
        elif delta < 0:
            if payments:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "payments are not allowed when exchange delta is negative"},
                )
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
        else:
            if payments or refund_payments:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "payments and refund_payments must be empty when exchange delta is zero"},
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
        for line in resolved_exchange_lines:
            snapshot = _legacy_snapshot(line)
            new_lines.append(
                PosSaleLine(
                    sale_id=exchange_sale.id,
                    tenant_id=scoped_tenant_id,
                    line_type=line.line_type,
                    qty=line.qty,
                    unit_price=float(_legacy_unit_price(line) or Decimal("0.00")),
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

        for line in resolved_exchange_lines:
            snapshot = _legacy_snapshot(line)
            if line.line_type == "EPC":
                stock_row = (
                    db.execute(
                        select(StockItem)
                        .where(
                            StockItem.tenant_id == sale.tenant_id,
                            StockItem.store_id == sale.store_id,
                            StockItem.epc == snapshot.epc,
                            StockItem.status != "SOLD",
                            StockItem.location_code == snapshot.location_code,
                            StockItem.pool == snapshot.pool,
                        )
                        .with_for_update()
                    )
                    .scalars()
                    .first()
                )
                if stock_row is None:
                    raise AppError(
                        ErrorCatalog.VALIDATION_ERROR,
                        details={"message": "insufficient RFID stock for exchange EPC line", "epc": snapshot.epc},
                    )
                stock_row.status = "SOLD"
                stock_row.item_status = "SOLD"
                stock_row.epc_status = "AVAILABLE"
                if stock_row.epc:
                    assignment = db.execute(
                        select(EpcAssignment).where(
                            EpcAssignment.tenant_id == sale.tenant_id,
                            EpcAssignment.item_uid == stock_row.item_uid,
                            EpcAssignment.epc == stock_row.epc,
                            EpcAssignment.active.is_(True),
                        )
                    ).scalars().first()
                    if assignment:
                        assignment.active = False
                        assignment.released_at = datetime.utcnow()
                        assignment.last_release_reason = "SOLD"
                        assignment.status = "RELEASED"
                        assignment.updated_at = datetime.utcnow()
                stock_row.location_is_vendible = False
                stock_row.updated_at = now
            elif line.line_type == "SKU":
                stock_rows = (
                    db.execute(
                        select(StockItem)
                        .where(
                            StockItem.tenant_id == sale.tenant_id,
                            StockItem.store_id == sale.store_id,
                            StockItem.sku == snapshot.sku,
                            StockItem.status != "SOLD",
                            StockItem.epc.is_(None),
                            StockItem.location_code == snapshot.location_code,
                            StockItem.pool == snapshot.pool,
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
                        details={"message": "insufficient stock for exchange SKU line", "sku": snapshot.sku},
                    )
                for stock_row in stock_rows:
                    stock_row.status = "SOLD"
                    stock_row.item_status = "SOLD"
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
                            StockItem.store_id == sale.store_id,
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
                            StockItem.store_id == sale.store_id,
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
                "exchange_lines": [line.model_dump(mode="json") for line in resolved_exchange_lines],
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
            movement_amount = cash_total
            if delta > 0:
                movement_amount = max(Decimal("0.00"), totals["cash_total"] - totals["change_due"])
            if movement_amount > 0:
                _record_cash_movement(
                    db,
                    session=cash_session,
                    tenant_id=scoped_tenant_id,
                    store_id=str(sale.store_id),
                    sale_id=sale.id,
                    action="CASH_OUT_REFUND" if delta < 0 else "SALE",
                    amount=movement_amount,
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
                store_id=effective_store_id,
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

    if action != "CHECKOUT":
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
        logger.info(
            "pos.sale.checkout.cash_validation.start tenant_id=%s store_id=%s cashier_user_id=%s sale_id=%s payment_method=%s trace_id=%s register_id=%s terminal_id=%s",
            scoped_tenant_id,
            str(sale.store_id),
            str(current_user.id),
            str(sale.id),
            "CASH",
            getattr(request.state, "trace_id", None),
            None,
            None,
        )
        cash_session = _require_open_cash_session(
            db,
            tenant_id=scoped_tenant_id,
            store_id=str(sale.store_id),
            cashier_user_id=str(current_user.id),
            trace_id=getattr(request.state, "trace_id", None),
            sale_id=str(sale.id),
        )

    now = datetime.utcnow()
    for line in lines:
        if line.line_type == "EPC":
            stock_row = (
                db.execute(
                    select(StockItem)
                    .where(
                        StockItem.tenant_id == sale.tenant_id,
                        StockItem.store_id == sale.store_id,
                        StockItem.epc == line.epc,
                        StockItem.status != "SOLD",
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
                    details={"message": "insufficient RFID stock for EPC line", "epc": line.epc},
                )
            line.item_uid = line.item_uid or stock_row.item_uid
            line.epc_at_sale = line.epc_at_sale or stock_row.epc or line.epc
            line.sku_snapshot = line.sku_snapshot or stock_row.sku
            line.description_snapshot = line.description_snapshot or stock_row.description
            line.var1_snapshot = line.var1_snapshot or stock_row.var1_value
            line.var2_snapshot = line.var2_snapshot or stock_row.var2_value
            if line.sale_price_snapshot is None:
                line.sale_price_snapshot = stock_row.sale_price
            stock_row.status = "SOLD"
            stock_row.item_status = "SOLD"
            stock_row.epc_status = "AVAILABLE"
            if stock_row.epc:
                assignment = db.execute(
                    select(EpcAssignment).where(
                        EpcAssignment.tenant_id == sale.tenant_id,
                        EpcAssignment.item_uid == stock_row.item_uid,
                        EpcAssignment.epc == stock_row.epc,
                        EpcAssignment.active.is_(True),
                    )
                ).scalars().first()
                if assignment:
                    assignment.active = False
                    assignment.released_at = datetime.utcnow()
                    assignment.last_release_reason = "SOLD"
                    assignment.status = "RELEASED"
                    assignment.updated_at = datetime.utcnow()
                stock_row.epc = None
            stock_row.location_is_vendible = False
            stock_row.updated_at = now
        elif line.line_type == "SKU":
            stock_rows = (
                db.execute(
                    select(StockItem)
                    .where(
                        StockItem.tenant_id == sale.tenant_id,
                        StockItem.store_id == sale.store_id,
                        StockItem.sku == line.sku,
                        StockItem.status != "SOLD",
                        StockItem.epc.is_(None),
                        StockItem.location_code == line.location_code,
                        StockItem.pool == line.pool,
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
                    details={"message": "insufficient stock for SKU line", "sku": line.sku},
                )
            for stock_row in stock_rows:
                stock_row.status = "SOLD"
                stock_row.item_status = "SOLD"
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
        net_cash_in = max(Decimal("0.00"), totals["cash_total"] - totals["change_due"])
        if net_cash_in > 0:
            _record_cash_movement(
                db,
                session=cash_session,
                tenant_id=scoped_tenant_id,
                store_id=str(sale.store_id),
                sale_id=sale.id,
                action="SALE",
                amount=net_cash_in,
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
            store_id=effective_store_id,
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
