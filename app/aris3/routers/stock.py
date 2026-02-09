from datetime import datetime
import re
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.aris3.core.deps import get_current_token_data, require_active_user, require_permission
from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.core.scope import is_superadmin
from app.aris3.db.session import get_db
from app.aris3.db.models import StockItem
from app.aris3.repos.stock import StockQueryFilters, StockRepository
from app.aris3.schemas.stock import (
    StockImportEpcRequest,
    StockImportResponse,
    StockImportSkuRequest,
    StockMigrateRequest,
    StockMigrateResponse,
    StockQueryMeta,
    StockQueryResponse,
    StockQueryTotals,
    StockRow,
)
from app.aris3.services.audit import AuditEventPayload, AuditService
from app.aris3.services.idempotency import IdempotencyService, extract_idempotency_key


router = APIRouter()
_EPC_PATTERN = re.compile(r"^[0-9A-F]{24}$")


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


def _require_transaction_id(transaction_id: str | None) -> None:
    if not transaction_id:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "transaction_id is required"},
        )


def _validate_epc(epc: str) -> None:
    if not _EPC_PATTERN.fullmatch(epc or ""):
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "epc must be 24 hex uppercase characters", "epc": epc},
        )


def _normalize_epc_optional(epc: str | None) -> str | None:
    if epc in (None, ""):
        return None
    return epc


def _validate_location_pool(line) -> None:
    if not line.location_code or not line.pool:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "location_code and pool are required"},
        )
    if line.location_is_vendible is False:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "location_is_vendible must be true for stock writes"},
        )


def _validate_expected_status(status: str | None, expected: str) -> None:
    if status != expected:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "status does not match expected pool", "expected": expected, "status": status},
        )


def _image_asset_uuid(asset_id: UUID | None) -> UUID | None:
    return asset_id if asset_id else None


@router.get("/aris3/stock", response_model=StockQueryResponse)
def list_stock(
    request: Request,
    token_data=Depends(get_current_token_data),
    _user=Depends(require_active_user),
    db=Depends(get_db),
    q: str | None = None,
    description: str | None = None,
    var1_value: str | None = None,
    var2_value: str | None = None,
    sku: str | None = None,
    epc: str | None = None,
    location_code: str | None = None,
    pool: str | None = None,
    tenant_id: str | None = None,
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    sort_by: str = Query("created_at"),
    sort_dir: Literal["asc", "desc"] = "desc",
):
    scoped_tenant_id = _resolve_tenant_id(token_data, tenant_id)
    repo = StockRepository(db)
    filters = StockQueryFilters(
        tenant_id=scoped_tenant_id,
        q=q,
        description=description,
        var1_value=var1_value,
        var2_value=var2_value,
        sku=sku,
        epc=epc,
        location_code=location_code,
        pool=pool,
        from_date=from_date,
        to_date=to_date,
    )
    rows, totals, resolved_sort_by = repo.list_stock(
        filters,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    response_rows = [
        StockRow(
            id=str(row.id),
            tenant_id=str(row.tenant_id),
            sku=row.sku,
            description=row.description,
            var1_value=row.var1_value,
            var2_value=row.var2_value,
            epc=row.epc,
            location_code=row.location_code,
            pool=row.pool,
            status=row.status,
            location_is_vendible=row.location_is_vendible,
            image_asset_id=str(row.image_asset_id) if row.image_asset_id else None,
            image_url=row.image_url,
            image_thumb_url=row.image_thumb_url,
            image_source=row.image_source,
            image_updated_at=row.image_updated_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]
    meta = StockQueryMeta(
        page=page,
        page_size=page_size,
        sort_by=resolved_sort_by,
        sort_dir=sort_dir,
    )
    return StockQueryResponse(
        meta=meta,
        rows=response_rows,
        totals=StockQueryTotals(**totals),
    )


@router.post("/aris3/stock/import-epc", response_model=StockImportResponse, status_code=201)
def import_stock_epc(
    request: Request,
    payload: StockImportEpcRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    _permission=Depends(require_permission("STORE_MANAGE")),
    db=Depends(get_db),
):
    _require_transaction_id(payload.transaction_id)
    scoped_tenant_id = _resolve_tenant_id(token_data, payload.tenant_id)
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
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "lines must not be empty"},
        )

    epcs = []
    seen_epcs: set[str] = set()
    for line in payload.lines:
        _validate_location_pool(line)
        _validate_expected_status(line.status, "RFID")
        if line.qty != 1:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "qty must be exactly 1 for EPC imports", "qty": line.qty},
            )
        if line.epc is None:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "epc is required for EPC imports"},
            )
        _validate_epc(line.epc)
        if line.epc in seen_epcs:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "duplicate epc in request", "epc": line.epc},
            )
        seen_epcs.add(line.epc)
        epcs.append(line.epc)

    existing_epcs = (
        db.execute(
            select(StockItem.epc).where(
                StockItem.tenant_id == scoped_tenant_id,
                StockItem.epc.in_(epcs),
            )
        )
        .scalars()
        .all()
    )
    if existing_epcs:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "epc already exists", "epcs": sorted(set(existing_epcs))},
        )

    items = [
        StockItem(
            tenant_id=scoped_tenant_id,
            sku=line.sku,
            description=line.description,
            var1_value=line.var1_value,
            var2_value=line.var2_value,
            epc=line.epc,
            location_code=line.location_code,
            pool=line.pool,
            status="RFID",
            location_is_vendible=line.location_is_vendible,
            image_asset_id=_image_asset_uuid(line.image_asset_id),
            image_url=line.image_url,
            image_thumb_url=line.image_thumb_url,
            image_source=line.image_source,
            image_updated_at=line.image_updated_at,
        )
        for line in payload.lines
    ]
    try:
        db.add_all(items)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "epc already exists"},
        )

    response = StockImportResponse(
        tenant_id=scoped_tenant_id,
        processed=len(items),
        trace_id=getattr(request.state, "trace_id", ""),
    )
    context.record_success(status_code=201, response_body=response.model_dump())
    AuditService(db).record_event(
        AuditEventPayload(
            tenant_id=scoped_tenant_id,
            user_id=str(current_user.id),
            store_id=str(current_user.store_id) if current_user.store_id else None,
            trace_id=getattr(request.state, "trace_id", "") or None,
            actor=current_user.username,
            action="stock.import_epc",
            entity_type="stock_item",
            entity_id="import-epc",
            before=None,
            after={"created": len(items), "epcs": epcs},
            metadata={"transaction_id": payload.transaction_id},
            result="success",
        )
    )
    return response


@router.post("/aris3/stock/import-sku", response_model=StockImportResponse, status_code=201)
def import_stock_sku(
    request: Request,
    payload: StockImportSkuRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    _permission=Depends(require_permission("STORE_MANAGE")),
    db=Depends(get_db),
):
    _require_transaction_id(payload.transaction_id)
    scoped_tenant_id = _resolve_tenant_id(token_data, payload.tenant_id)
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
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "lines must not be empty"},
        )

    items: list[StockItem] = []
    for line in payload.lines:
        _validate_location_pool(line)
        _validate_expected_status(line.status, "PENDING")
        if line.qty < 1:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "qty must be at least 1", "qty": line.qty},
            )
        normalized_epc = _normalize_epc_optional(line.epc)
        if normalized_epc:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "epc must be empty for SKU imports", "epc": line.epc},
            )
        for _ in range(line.qty):
            items.append(
                StockItem(
                    tenant_id=scoped_tenant_id,
                    sku=line.sku,
                    description=line.description,
                    var1_value=line.var1_value,
                    var2_value=line.var2_value,
                    epc=None,
                    location_code=line.location_code,
                    pool=line.pool,
                    status="PENDING",
                    location_is_vendible=line.location_is_vendible,
                    image_asset_id=_image_asset_uuid(line.image_asset_id),
                    image_url=line.image_url,
                    image_thumb_url=line.image_thumb_url,
                    image_source=line.image_source,
                    image_updated_at=line.image_updated_at,
                )
            )

    db.add_all(items)
    db.commit()

    response = StockImportResponse(
        tenant_id=scoped_tenant_id,
        processed=len(items),
        trace_id=getattr(request.state, "trace_id", ""),
    )
    context.record_success(status_code=201, response_body=response.model_dump())
    AuditService(db).record_event(
        AuditEventPayload(
            tenant_id=scoped_tenant_id,
            user_id=str(current_user.id),
            store_id=str(current_user.store_id) if current_user.store_id else None,
            trace_id=getattr(request.state, "trace_id", "") or None,
            actor=current_user.username,
            action="stock.import_sku",
            entity_type="stock_item",
            entity_id="import-sku",
            before=None,
            after={"created": len(items)},
            metadata={"transaction_id": payload.transaction_id},
            result="success",
        )
    )
    return response


@router.post("/aris3/stock/migrate-sku-to-epc", response_model=StockMigrateResponse)
def migrate_stock_sku_to_epc(
    request: Request,
    payload: StockMigrateRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    _permission=Depends(require_permission("STORE_MANAGE")),
    db=Depends(get_db),
):
    _require_transaction_id(payload.transaction_id)
    scoped_tenant_id = _resolve_tenant_id(token_data, payload.tenant_id)
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

    _validate_location_pool(payload.data)
    _validate_expected_status(payload.data.status, "PENDING")
    _validate_epc(payload.epc)
    existing_epc = db.execute(
        select(StockItem.id).where(
            StockItem.tenant_id == scoped_tenant_id,
            StockItem.epc == payload.epc,
        )
    ).scalar_one_or_none()
    if existing_epc:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "epc already exists", "epc": payload.epc},
        )

    pending_row = (
        db.execute(
            select(StockItem)
            .where(
                StockItem.tenant_id == scoped_tenant_id,
                StockItem.status == "PENDING",
                StockItem.sku == payload.data.sku,
                StockItem.description == payload.data.description,
                StockItem.var1_value == payload.data.var1_value,
                StockItem.var2_value == payload.data.var2_value,
                (StockItem.epc.is_(None) if payload.data.epc is None else StockItem.epc == payload.data.epc),
                StockItem.location_code == payload.data.location_code,
                StockItem.pool == payload.data.pool,
                StockItem.location_is_vendible == payload.data.location_is_vendible,
                StockItem.image_asset_id == _image_asset_uuid(payload.data.image_asset_id),
                StockItem.image_url == payload.data.image_url,
                StockItem.image_thumb_url == payload.data.image_thumb_url,
                StockItem.image_source == payload.data.image_source,
                StockItem.image_updated_at == payload.data.image_updated_at,
            )
            .with_for_update()
            .order_by(StockItem.created_at.asc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    if not pending_row:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "no pending stock available for migration"},
        )
    pending_row.epc = payload.epc
    pending_row.status = "RFID"
    pending_row.updated_at = datetime.utcnow()
    db.commit()

    response = StockMigrateResponse(
        tenant_id=scoped_tenant_id,
        migrated=1,
        trace_id=getattr(request.state, "trace_id", ""),
    )
    context.record_success(status_code=200, response_body=response.model_dump())
    AuditService(db).record_event(
        AuditEventPayload(
            tenant_id=scoped_tenant_id,
            user_id=str(current_user.id),
            store_id=str(current_user.store_id) if current_user.store_id else None,
            trace_id=getattr(request.state, "trace_id", "") or None,
            actor=current_user.username,
            action="stock.migrate_sku_to_epc",
            entity_type="stock_item",
            entity_id=f"migrate:{payload.data.sku}:{payload.data.location_code}",
            before={"status": "PENDING"},
            after={"status": "RFID", "epc": payload.epc},
            metadata={"transaction_id": payload.transaction_id},
            result="success",
        )
    )
    return response
