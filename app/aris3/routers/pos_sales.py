from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import delete, select

from app.aris3.core.deps import get_current_token_data, require_active_user, require_permission
from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.core.scope import (
    DEFAULT_BROAD_STORE_ROLES,
    enforce_store_scope,
    enforce_tenant_scope,
    is_superadmin,
)
from app.aris3.db.models import (
    PosCashMovement,
    PosCashSession,
    PosPayment,
    PosSale,
    PosSaleLine,
    StockItem,
)
from app.aris3.db.session import get_db
from app.aris3.repos.pos_sales import PosSaleQueryFilters, PosSaleRepository
from app.aris3.schemas.pos_sales import (
    PosPaymentCreate,
    PosPaymentResponse,
    PosPaymentSummary,
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
from app.aris3.services.audit import AuditEventPayload, AuditService
from app.aris3.services.idempotency import IdempotencyService, extract_idempotency_key


router = APIRouter()


def _require_transaction_id(transaction_id: str | None) -> None:
    if not transaction_id:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "transaction_id is required"},
        )


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


def _require_open_cash_session(db, *, tenant_id: str, store_id: str, cashier_user_id: str) -> PosCashSession:
    session = (
        db.execute(
            select(PosCashSession).where(
                PosCashSession.tenant_id == tenant_id,
                PosCashSession.store_id == store_id,
                PosCashSession.cashier_user_id == cashier_user_id,
                PosCashSession.status == "OPEN",
            )
        )
        .scalars()
        .first()
    )
    if session is None:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "open cash session required for CASH payments"},
        )
    return session


def _sale_line_response(line: PosSaleLine) -> PosSaleLineResponse:
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
    header = PosSaleHeaderResponse(
        id=_normalize_uuid(sale.id),
        tenant_id=_normalize_uuid(sale.tenant_id),
        store_id=_normalize_uuid(sale.store_id),
        status=sale.status,
        total_due=Decimal(str(sale.total_due)),
        paid_total=Decimal(str(sale.paid_total)),
        balance_due=Decimal(str(sale.balance_due)),
        change_due=Decimal(str(sale.change_due)),
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
        lines=[_sale_line_response(line) for line in lines],
        payments=[_payment_response(payment) for payment in payments],
        payment_summary=_payment_summary(payments),
    )


@router.get("/aris3/pos/sales", response_model=PosSaleListResponse)
def list_sales(
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
    rows = repo.list_sales(PosSaleQueryFilters(tenant_id=scoped_tenant_id, store_id=store_id))
    responses = [_sale_response(repo, sale) for sale in rows]
    return PosSaleListResponse(rows=responses)


@router.post("/aris3/pos/sales", response_model=PosSaleResponse, status_code=201)
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
    enforce_store_scope(token_data, payload.store_id, db, allow_superadmin=True)

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
    for line in payload.lines:
        _validate_sale_snapshot(line)

    totals = _sale_totals(payload.lines)
    sale = PosSale(
        tenant_id=scoped_tenant_id,
        store_id=payload.store_id,
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
    for line in payload.lines:
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


@router.patch("/aris3/pos/sales/{sale_id}", response_model=PosSaleResponse)
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
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "sale not found"})
    if str(sale.tenant_id) != scoped_tenant_id:
        raise AppError(ErrorCatalog.CROSS_TENANT_ACCESS_DENIED)
    enforce_store_scope(token_data, str(sale.store_id), db, allow_superadmin=True)
    if sale.status != "DRAFT":
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "sale must be DRAFT to update"})

    before = {"total_due": str(sale.total_due), "lines": len(PosSaleRepository(db).get_lines(sale_id))}
    if payload.lines is not None:
        if not payload.lines:
            raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "lines must not be empty"})
        for line in payload.lines:
            _validate_sale_snapshot(line)
        db.execute(delete(PosSaleLine).where(PosSaleLine.sale_id == sale.id))
        lines = []
        for line in payload.lines:
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
        totals = _sale_totals(payload.lines)
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


@router.get("/aris3/pos/sales/{sale_id}", response_model=PosSaleResponse)
def get_sale(
    sale_id: str,
    token_data=Depends(get_current_token_data),
    _user=Depends(require_active_user),
    _permission=Depends(require_permission("POS_SALE_VIEW")),
    db=Depends(get_db),
):
    sale = PosSaleRepository(db).get_by_id(sale_id)
    if sale is None:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "sale not found"})
    scoped_tenant_id = _resolve_tenant_id(token_data, str(sale.tenant_id))
    if str(sale.tenant_id) != scoped_tenant_id:
        raise AppError(ErrorCatalog.CROSS_TENANT_ACCESS_DENIED)
    enforce_store_scope(token_data, str(sale.store_id), db, allow_superadmin=True)
    repo = PosSaleRepository(db)
    return _sale_response(repo, sale)


@router.post("/aris3/pos/sales/{sale_id}/actions", response_model=PosSaleResponse)
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
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "sale not found"})
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

    if payload.action != "checkout":
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "unsupported action"})
    if sale.status != "DRAFT":
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "sale must be DRAFT to checkout"})

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
        db.add(
            PosCashMovement(
                tenant_id=scoped_tenant_id,
                store_id=sale.store_id,
                cash_session_id=cash_session.id,
                sale_id=sale.id,
                action="SALE",
                amount=float(totals["cash_total"]),
            )
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
