from datetime import datetime, timezone
import logging
import re
from typing import Literal
from uuid import UUID
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import String, cast, select
from sqlalchemy.exc import IntegrityError, ProgrammingError

from app.aris3.core.deps import get_current_token_data, require_active_user, require_permission
from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.core.scope import can_write_stock_or_assets, is_superadmin
from app.aris3.db.session import get_db
from app.aris3.db.models import EpcAssignment, PreloadLine, PreloadSession, SkuImage, StockItem, Store
from app.aris3.repos.stock import StockQueryFilters, StockRepository
from app.aris3.schemas.stock import (
    StockImportEpcRequest,
    StockImportResponse,
    StockImportSkuRequest,
    StockActionEpcLifecyclePayload,
    StockActionMarkdownPayload,
    StockActionRepricePayload,
    StockActionReprintPayload,
    StockActionReplaceEpcPayload,
    StockActionRequest,
    StockActionResponse,
    StockActionWriteOffPayload,
    StockMigrateRequest,
    StockMigrateResponse,
    EpcAssignmentHistoryResponse,
    EpcReleaseRequest,
    EpcReleaseResponse,
    ItemIssueRequest,
    ItemIssueResolveResponse,
    ItemIssueResolveRequest,
    ItemIssueResponse,
    PendingEpcAssignRequest,
    PreloadLinePatchRequest,
    PreloadLineResponse,
    PreloadSessionCreateRequest,
    PreloadSessionResponse,
    SkuImageResponse,
    SkuImageUpsertRequest,
    StockQueryMeta,
    StockQueryResponse,
    StockQueryTotals,
    StockRow,
)
from app.aris3.schemas.errors import ApiErrorResponse
from app.aris3.services.audit import AuditEventPayload, AuditService
from app.aris3.services.idempotency import IdempotencyService, extract_idempotency_key
from app.aris3.services.stock_rules import compute_operational_state


router = APIRouter()
logger = logging.getLogger(__name__)
_EPC_PATTERN = re.compile(r"^[0-9A-F]{24}$")
_IN_TRANSIT_CODE = "IN_TRANSIT"
_DEFAULT_IMPORT_POOL = "BODEGA"
_DEFAULT_IMPORT_LOCATION = "WH-MAIN"
_IDEMPOTENCY_HEADER_PARAMETER = {
    "name": "Idempotency-Key",
    "in": "header",
    "required": False,
    "schema": {"type": "string"},
    "description": "Optional key for safe client retries of mutating requests.",
}


def _apply_import_defaults(line) -> None:
    if not line.pool:
        line.pool = _DEFAULT_IMPORT_POOL
    if not line.location_code:
        line.location_code = _DEFAULT_IMPORT_LOCATION
    if line.location_is_vendible is None:
        line.location_is_vendible = False


def _validate_location_pool_for_import(line) -> None:
    if not line.location_code or not line.pool:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "location_code and pool are required"},
        )


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


def _require_tenant_admin(token_data) -> None:
    if can_write_stock_or_assets(token_data.role):
        return
    raise AppError(ErrorCatalog.PERMISSION_DENIED)


def _validate_scoped_store(db, *, tenant_id: str, store_id: str) -> None:
    store_exists = db.execute(
        select(Store.id).where(Store.id == store_id, Store.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if not store_exists:
        raise AppError(
            ErrorCatalog.CROSS_TENANT_ACCESS_DENIED,
            details={"message": "store_id is outside tenant scope", "store_id": store_id},
        )

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


def _require_location_pool(line) -> None:
    if not line.location_code or not line.pool:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "location_code and pool are required"},
        )


def _validate_non_negative_prices(line) -> None:
    for field in ("cost_price", "suggested_price", "sale_price"):
        value = getattr(line, field, None)
        if value is not None and value < 0:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": f"{field} must be greater than or equal to 0", field: str(value)},
            )


def _validate_expected_status(status: str | None, expected: str) -> None:
    if status != expected:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "status does not match expected pool", "expected": expected, "status": status},
        )


def _image_asset_uuid(asset_id: UUID | None) -> UUID | None:
    return asset_id if asset_id else None


def _normalize_utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _commit_stock_items(db, *, operation: str, trace_id: str | None = None) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "epc already exists"},
        )
    except ProgrammingError as exc:
        db.rollback()
        logger.exception(
            "Stock %s failed due to DB programming error trace_id=%s",
            operation,
            trace_id or "",
        )
        message = str(getattr(exc, "orig", exc)).lower()
        if "column" in message and ("does not exist" in message or "undefined" in message):
            logger.error(
                "Stock %s schema mismatch detected trace_id=%s detail=%s",
                operation,
                trace_id or "",
                str(getattr(exc, "orig", exc)),
            )
            raise AppError(
                ErrorCatalog.DB_UNAVAILABLE,
                details={
                    "message": "database schema is not aligned with stock import contract",
                    "type": "SCHEMA_MISMATCH",
                },
            )
        raise AppError(
            ErrorCatalog.DB_UNAVAILABLE,
            details={
                "message": "database programming error while processing stock operation",
                "type": "PROGRAMMING_ERROR",
            },
        )


def _import_sku_payload_summary(payload: StockImportSkuRequest) -> dict:
    line_summaries = []
    for line in payload.lines:
        line_summaries.append(
            {
                "store_id": line.store_id,
                "sku": line.sku,
                "qty": line.qty,
                "status": line.status,
                "has_epc": bool(_normalize_epc_optional(line.epc)),
                "has_image_asset_id": bool(line.image_asset_id),
                "has_image_url": bool(line.image_url),
                "has_image_thumb_url": bool(line.image_thumb_url),
                "has_image_source": bool(line.image_source),
                "has_image_updated_at": bool(line.image_updated_at),
            }
        )
    return {
        "transaction_id": payload.transaction_id,
        "tenant_id": payload.tenant_id,
        "lines_count": len(payload.lines),
        "lines": line_summaries,
    }


def _is_in_transit(location_code: str | None, pool: str | None) -> bool:
    return location_code == _IN_TRANSIT_CODE or pool == _IN_TRANSIT_CODE


def _stock_snapshot(row: StockItem) -> dict:
    return {
        "sku": row.sku,
        "description": row.description,
        "var1_value": row.var1_value,
        "var2_value": row.var2_value,
        "cost_price": row.cost_price,
        "suggested_price": row.suggested_price,
        "sale_price": row.sale_price,
        "epc": row.epc,
        "location_code": row.location_code,
        "pool": row.pool,
        "store_id": str(row.store_id) if row.store_id else None,
        "status": row.status,
        "location_is_vendible": row.location_is_vendible,
        "image_asset_id": str(row.image_asset_id) if row.image_asset_id else None,
        "image_url": row.image_url,
        "image_thumb_url": row.image_thumb_url,
        "image_source": row.image_source,
        "image_updated_at": row.image_updated_at,
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _build_stock_match_filter(scoped_tenant_id: str, data):
    return (
        StockItem.tenant_id == scoped_tenant_id,
        StockItem.sku == data.sku,
        StockItem.description == data.description,
        StockItem.var1_value == data.var1_value,
        StockItem.var2_value == data.var2_value,
        (StockItem.epc.is_(None) if data.epc is None else StockItem.epc == data.epc),
        StockItem.location_code == data.location_code,
        StockItem.pool == data.pool,
        (StockItem.store_id.is_(None) if data.store_id is None else StockItem.store_id == data.store_id),
        StockItem.status == data.status,
        StockItem.location_is_vendible == data.location_is_vendible,
        StockItem.image_asset_id == _image_asset_uuid(data.image_asset_id),
        StockItem.image_url == data.image_url,
        StockItem.image_thumb_url == data.image_thumb_url,
        StockItem.image_source == data.image_source,
        StockItem.image_updated_at == _normalize_utc_datetime(data.image_updated_at),
    )


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
    store_id: str | None = None,
    tenant_id: str | None = None,
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    sort_by: str = Query("created_at"),
    sort_dir: Literal["asc", "desc"] = "desc",
    view: Literal["operational", "history", "all"] = Query("operational"),
    include_sold: bool | None = Query(default=None),
):
    scoped_tenant_id = _resolve_tenant_id(token_data, tenant_id)
    if store_id:
        _validate_scoped_store(db, tenant_id=scoped_tenant_id, store_id=store_id)
    if include_sold is True and view == "operational":
        view = "all"
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
        store_id=store_id,
        from_date=from_date,
        to_date=to_date,
        view=view,
    )
    rows, totals, resolved_sort_by = repo.list_stock(
        filters,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    if store_id:
        scoped_store_id = UUID(store_id)
        rows = [row for row in rows if row.store_id == scoped_store_id]

    sku_available_qty: dict[tuple[str | None, str | None], int] = {}
    for row in rows:
        state = compute_operational_state(row)
        if state.sale_mode != "SKU" and state.transfer_mode != "SKU":
            continue
        key = (str(row.store_id) if row.store_id else None, row.sku)
        sku_available_qty[key] = sku_available_qty.get(key, 0) + 1

    response_rows = []
    for row in rows:
        state = compute_operational_state(row)
        key = (str(row.store_id) if row.store_id else None, row.sku)
        sku_mode = state.sale_mode == "SKU" or state.transfer_mode == "SKU"
        available_qty = sku_available_qty.get(key, 0) if sku_mode else (1 if state.available_for_sale else 0)
        response_rows.append(StockRow(
            sku=row.sku,
            description=row.description,
            var1_value=row.var1_value,
            var2_value=row.var2_value,
            cost_price=row.cost_price,
            suggested_price=row.suggested_price,
            sale_price=row.sale_price,
            epc=row.epc,
            location_code=row.location_code,
            pool=row.pool,
            store_id=str(row.store_id) if row.store_id else None,
            status=row.status,
            location_is_vendible=row.location_is_vendible,
            image_asset_id=str(row.image_asset_id) if row.image_asset_id else None,
            image_url=row.image_url,
            image_thumb_url=row.image_thumb_url,
            image_source=row.image_source,
            image_updated_at=row.image_updated_at,
            available_for_sale=state.available_for_sale,
            available_for_transfer=state.available_for_transfer,
            sale_mode=state.sale_mode,
            transfer_mode=state.transfer_mode,
            is_historical=state.is_historical,
            available_qty=available_qty,
            display_pool=row.pool,
            display_location_code=row.location_code,
            id=str(row.id),
            tenant_id=str(row.tenant_id),
            created_at=row.created_at,
            updated_at=row.updated_at,
        ))
    meta = StockQueryMeta(
        page=page,
        page_size=page_size,
        sort_by=resolved_sort_by,
        sort_dir=sort_dir,
        view=view,
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
    _require_tenant_admin(token_data)
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
        _apply_import_defaults(line)
        _validate_location_pool_for_import(line)
        if line.store_id:
            _validate_scoped_store(db, tenant_id=scoped_tenant_id, store_id=line.store_id)
        _validate_non_negative_prices(line)
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
            store_id=line.store_id,
            status="RFID",
            location_is_vendible=line.location_is_vendible,
            image_asset_id=_image_asset_uuid(line.image_asset_id),
            image_url=line.image_url,
            image_thumb_url=line.image_thumb_url,
            image_source=line.image_source,
            image_updated_at=_normalize_utc_datetime(line.image_updated_at),
            cost_price=line.cost_price,
            suggested_price=line.suggested_price,
            sale_price=line.sale_price,
        )
        for line in payload.lines
    ]
    db.add_all(items)
    _commit_stock_items(db, operation="import-epc", trace_id=getattr(request.state, "trace_id", ""))

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
    _require_tenant_admin(token_data)
    _require_transaction_id(payload.transaction_id)
    scoped_tenant_id = _resolve_tenant_id(token_data, payload.tenant_id)
    idempotency_key = extract_idempotency_key(request.headers, required=False) or str(uuid4())
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
    logger.info(
        "Processing stock import-sku request",
        extra={
            "trace_id": getattr(request.state, "trace_id", ""),
            "tenant_id": scoped_tenant_id,
            "payload": _import_sku_payload_summary(payload),
        },
    )

    if not payload.lines:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "lines must not be empty"},
        )

    items: list[StockItem] = []
    for line in payload.lines:
        _apply_import_defaults(line)
        _validate_location_pool_for_import(line)
        if not line.store_id:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "store_id is required", "field": "lines[].store_id"},
            )
        if not line.sku:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "sku is required", "field": "lines[].sku"},
            )
        _validate_scoped_store(db, tenant_id=scoped_tenant_id, store_id=line.store_id)
        _validate_non_negative_prices(line)
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
                    store_id=line.store_id,
                    status="PENDING",
                    location_is_vendible=line.location_is_vendible,
                    image_asset_id=_image_asset_uuid(line.image_asset_id),
                    image_url=line.image_url,
                    image_thumb_url=line.image_thumb_url,
                    image_source=line.image_source,
                    image_updated_at=_normalize_utc_datetime(line.image_updated_at),
                    cost_price=line.cost_price,
                    suggested_price=line.suggested_price,
                    sale_price=line.sale_price,
                )
            )

    db.add_all(items)
    _commit_stock_items(db, operation="import-sku", trace_id=getattr(request.state, "trace_id", ""))

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
    _require_tenant_admin(token_data)
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
    if payload.data.store_id:
        _validate_scoped_store(db, tenant_id=scoped_tenant_id, store_id=payload.data.store_id)
    _validate_non_negative_prices(payload.data)
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
                (
                    StockItem.store_id.is_(None)
                    if payload.data.store_id is None
                    else StockItem.store_id == payload.data.store_id
                ),
                StockItem.location_is_vendible == payload.data.location_is_vendible,
                StockItem.image_asset_id == _image_asset_uuid(payload.data.image_asset_id),
                StockItem.image_url == payload.data.image_url,
                StockItem.image_thumb_url == payload.data.image_thumb_url,
                StockItem.image_source == payload.data.image_source,
                StockItem.image_updated_at == _normalize_utc_datetime(payload.data.image_updated_at),
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
    pending_row.cost_price = payload.data.cost_price if payload.data.cost_price is not None else pending_row.cost_price
    pending_row.suggested_price = (
        payload.data.suggested_price if payload.data.suggested_price is not None else pending_row.suggested_price
    )
    pending_row.sale_price = payload.data.sale_price if payload.data.sale_price is not None else pending_row.sale_price
    pending_row.store_id = payload.data.store_id
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


@router.post("/aris3/stock/actions", response_model=StockActionResponse)
def stock_actions(
    request: Request,
    payload: StockActionRequest,
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

    action = payload.action
    processed = 0
    before_payload: dict | None = None
    after_payload: dict | None = None
    metadata: dict | None = {"transaction_id": payload.transaction_id}
    now = datetime.utcnow()

    try:
        if action == "WRITE_OFF":
            action_payload = StockActionWriteOffPayload(**payload.payload)
            if action_payload.reason:
                metadata["reason"] = action_payload.reason
            data = action_payload.data
            _require_location_pool(data)
            if data.status not in {"RFID", "PENDING"}:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "status must be RFID or PENDING", "status": data.status},
                )
            if action_payload.qty < 1:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "qty must be at least 1", "qty": action_payload.qty},
                )
            if action_payload.reason and action_payload.reason.upper() == "LOST":
                if _is_in_transit(data.location_code, data.pool):
                    raise AppError(
                        ErrorCatalog.VALIDATION_ERROR,
                        details={"message": "lost write-off not allowed for IN_TRANSIT locations"},
                    )
            if data.status == "RFID":
                if action_payload.qty != 1:
                    raise AppError(
                        ErrorCatalog.VALIDATION_ERROR,
                        details={"message": "qty must be 1 for RFID write-off", "qty": action_payload.qty},
                    )
                if not data.epc:
                    raise AppError(
                        ErrorCatalog.VALIDATION_ERROR,
                        details={"message": "epc is required for RFID write-off"},
                    )
                _validate_epc(data.epc)
                row = (
                    db.execute(
                        select(StockItem)
                        .where(StockItem.tenant_id == scoped_tenant_id, StockItem.epc == data.epc)
                        .with_for_update()
                    )
                    .scalars()
                    .first()
                )
                if not row:
                    raise AppError(
                        ErrorCatalog.VALIDATION_ERROR,
                        details={"message": "stock item not found", "epc": data.epc},
                    )
                if (
                    row.location_code != data.location_code
                    or row.pool != data.pool
                    or row.status != data.status
                    or row.location_is_vendible != data.location_is_vendible
                ):
                    raise AppError(
                        ErrorCatalog.VALIDATION_ERROR,
                        details={"message": "pool/location/status mismatch for write-off"},
                    )
                before_payload = {"removed": [_stock_snapshot(row)]}
                db.delete(row)
                processed = 1
            else:
                if data.epc is not None:
                    raise AppError(
                        ErrorCatalog.VALIDATION_ERROR,
                        details={"message": "epc must be empty for PENDING write-off"},
                    )
                rows = (
                    db.execute(
                        select(StockItem)
                        .where(*_build_stock_match_filter(scoped_tenant_id, data))
                        .with_for_update()
                        .order_by(StockItem.created_at.asc())
                        .limit(action_payload.qty)
                    )
                    .scalars()
                    .all()
                )
                if len(rows) < action_payload.qty:
                    raise AppError(
                        ErrorCatalog.VALIDATION_ERROR,
                        details={"message": "insufficient pending stock for write-off"},
                    )
                before_payload = {"removed": [_stock_snapshot(row) for row in rows]}
                for row in rows:
                    db.delete(row)
                processed = len(rows)
            after_payload = {"removed": processed}
        elif action == "REPRICE":
            action_payload = StockActionRepricePayload(**payload.payload)
            if action_payload.price is not None:
                metadata["price"] = action_payload.price
            if action_payload.currency:
                metadata["currency"] = action_payload.currency
            data = action_payload.data
            _require_location_pool(data)
            row = (
                db.execute(
                    select(StockItem)
                    .where(*_build_stock_match_filter(scoped_tenant_id, data))
                    .with_for_update()
                )
                .scalars()
                .first()
            )
            if not row:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "stock item not found for repricing"},
                )
            before_payload = _stock_snapshot(row)
            after_payload = {**before_payload, "price": action_payload.price, "currency": action_payload.currency}
            processed = 1
        elif action == "MARKDOWN_BY_AGE":
            action_payload = StockActionMarkdownPayload(**payload.payload)
            if action_payload.policy:
                metadata["policy"] = action_payload.policy
            data = action_payload.data
            _require_location_pool(data)
            row = (
                db.execute(
                    select(StockItem)
                    .where(*_build_stock_match_filter(scoped_tenant_id, data))
                    .with_for_update()
                )
                .scalars()
                .first()
            )
            if not row:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "stock item not found for markdown"},
                )
            before_payload = _stock_snapshot(row)
            after_payload = {**before_payload, "policy": action_payload.policy}
            processed = 1
        elif action == "REPRINT_LABEL":
            action_payload = StockActionReprintPayload(**payload.payload)
            data = action_payload.data
            _require_location_pool(data)
            row = (
                db.execute(
                    select(StockItem)
                    .where(*_build_stock_match_filter(scoped_tenant_id, data))
                    .with_for_update()
                )
                .scalars()
                .first()
            )
            if not row:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "stock item not found for reprint"},
                )
            before_payload = _stock_snapshot(row)
            after_payload = before_payload
            processed = 1
        elif action == "REPLACE_EPC":
            action_payload = StockActionReplaceEpcPayload(**payload.payload)
            if action_payload.reason:
                metadata["reason"] = action_payload.reason
            if action_payload.current_epc == action_payload.new_epc:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "new_epc must differ from current_epc"},
                )
            _validate_epc(action_payload.current_epc)
            _validate_epc(action_payload.new_epc)
            existing_epc = db.execute(
                select(StockItem.id).where(
                    StockItem.tenant_id == scoped_tenant_id,
                    StockItem.epc == action_payload.new_epc,
                )
            ).scalar_one_or_none()
            if existing_epc:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "epc already exists", "epc": action_payload.new_epc},
                )
            row = (
                db.execute(
                    select(StockItem)
                    .where(
                        StockItem.tenant_id == scoped_tenant_id,
                        StockItem.epc == action_payload.current_epc,
                    )
                    .with_for_update()
                )
                .scalars()
                .first()
            )
            if not row:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "stock item not found", "epc": action_payload.current_epc},
                )
            if row.status != "RFID":
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "status must be RFID to replace epc", "status": row.status},
                )
            before_payload = _stock_snapshot(row)
            row.epc = action_payload.new_epc
            row.updated_at = now
            after_payload = _stock_snapshot(row)
            processed = 1
        elif action in {"MARK_EPC_DAMAGED", "RETIRE_EPC", "RETURN_EPC_TO_POOL"}:
            action_payload = StockActionEpcLifecyclePayload(**payload.payload)
            if action_payload.reason:
                metadata["reason"] = action_payload.reason
            if action_payload.epc_type:
                metadata["epc_type"] = action_payload.epc_type
            _validate_epc(action_payload.epc)
            row = (
                db.execute(
                    select(StockItem)
                    .where(StockItem.tenant_id == scoped_tenant_id, StockItem.epc == action_payload.epc)
                    .with_for_update()
                )
                .scalars()
                .first()
            )
            if not row:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "stock item not found", "epc": action_payload.epc},
                )
            if row.status != "RFID":
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "status must be RFID for EPC lifecycle action", "status": row.status},
                )
            if action == "RETURN_EPC_TO_POOL":
                if action_payload.epc_type is None:
                    raise AppError(
                        ErrorCatalog.VALIDATION_ERROR,
                        details={"message": "epc_type is required to return to pool"},
                    )
                if action_payload.epc_type == "NON_REUSABLE_LABEL":
                    raise AppError(
                        ErrorCatalog.VALIDATION_ERROR,
                        details={"message": "non reusable labels cannot be returned to pool"},
                    )
            before_payload = _stock_snapshot(row)
            row.epc = None
            row.status = "PENDING"
            row.updated_at = now
            after_payload = _stock_snapshot(row)
            processed = 1
        else:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "unsupported action", "action": action},
            )
    except ValidationError as exc:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "invalid action payload", "errors": exc.errors()},
        ) from exc

    db.commit()
    response = StockActionResponse(
        tenant_id=scoped_tenant_id,
        action=action,
        processed=processed,
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
            action=f"stock.{action.lower()}",
            entity_type="stock_item",
            entity_id=action,
            before=before_payload,
            after=after_payload,
            metadata=metadata,
            result="success",
        )
    )
    return response


def _preload_line_response(line: PreloadLine) -> PreloadLineResponse:
    return PreloadLineResponse(
        id=str(line.id), preload_session_id=str(line.preload_session_id), item_uid=str(line.item_uid), tenant_id=str(line.tenant_id),
        store_id=str(line.store_id) if line.store_id else None, sku=line.sku, epc=line.epc, description=line.description,
        var1_value=line.var1_value, var2_value=line.var2_value, pool=line.pool, location_code=line.location_code,
        vendible=line.vendible, cost_price=line.cost_price, suggested_price=line.suggested_price, sale_price=line.sale_price,
        item_status=line.item_status, epc_status=line.epc_status, observation=line.observation, image_mode=line.image_mode,
        image_asset_id=str(line.image_asset_id) if line.image_asset_id else None, print_status=line.print_status,
        source_file_name=line.source_file_name, source_row_number=line.source_row_number, lifecycle_state=line.lifecycle_state,
        saved_stock_item_id=str(line.saved_stock_item_id) if line.saved_stock_item_id else None, created_at=line.created_at, updated_at=line.updated_at,
    )


@router.post(
    "/aris3/stock/preload-sessions",
    response_model=PreloadSessionResponse,
    status_code=201,
)
def create_preload_session(payload: PreloadSessionCreateRequest, token_data=Depends(get_current_token_data), _user=Depends(require_active_user), db=Depends(get_db)):
    scoped_tenant_id = _resolve_tenant_id(token_data, payload.tenant_id)
    _require_tenant_admin(token_data)
    now = datetime.utcnow()
    session = PreloadSession(tenant_id=scoped_tenant_id, store_id=payload.store_id, source_file_name=payload.source_file_name, created_by_user_id=token_data.sub, created_at=now, updated_at=now)
    db.add(session)
    db.flush()
    for row in payload.lines:
        for _ in range(max(1, row.qty)):
            db.add(PreloadLine(preload_session_id=session.id, tenant_id=scoped_tenant_id, store_id=payload.store_id, sku=row.sku, epc=_normalize_epc_optional(row.epc), description=row.description, var1_value=row.var1_value, var2_value=row.var2_value, pool=row.pool, location_code=row.location_code, vendible=row.vendible, cost_price=row.cost_price, suggested_price=row.suggested_price, sale_price=row.sale_price, item_status="PENDING", epc_status="AVAILABLE", observation=row.observation, image_mode=row.image_mode, image_asset_id=row.image_asset_id, source_file_name=payload.source_file_name, source_row_number=row.source_row_number, lifecycle_state="STAGING", created_at=now, updated_at=now))
    db.commit()
    lines = db.execute(select(PreloadLine).where(PreloadLine.preload_session_id == session.id).order_by(PreloadLine.created_at)).scalars().all()
    return PreloadSessionResponse(id=str(session.id), tenant_id=str(session.tenant_id), store_id=str(session.store_id) if session.store_id else None, source_file_name=session.source_file_name, status=session.status, created_at=session.created_at, updated_at=session.updated_at, lines=[_preload_line_response(line) for line in lines])


@router.get("/aris3/stock/preload-sessions/{session_id}", response_model=PreloadSessionResponse)
def get_preload_session(session_id: str, tenant_id: str | None = None, token_data=Depends(get_current_token_data), _user=Depends(require_active_user), db=Depends(get_db)):
    scoped_tenant_id = _resolve_tenant_id(token_data, tenant_id)
    session = db.get(PreloadSession, session_id)
    if not session or str(session.tenant_id) != scoped_tenant_id:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "preload session not found", "session_id": session_id})
    lines = db.execute(select(PreloadLine).where(PreloadLine.preload_session_id == session.id).order_by(PreloadLine.created_at)).scalars().all()
    return PreloadSessionResponse(id=str(session.id), tenant_id=str(session.tenant_id), store_id=str(session.store_id) if session.store_id else None, source_file_name=session.source_file_name, status=session.status, created_at=session.created_at, updated_at=session.updated_at, lines=[_preload_line_response(line) for line in lines])


@router.patch("/aris3/stock/preload-lines/{line_id}", response_model=PreloadLineResponse)
def patch_preload_line(line_id: str, payload: PreloadLinePatchRequest, tenant_id: str | None = None, token_data=Depends(get_current_token_data), _user=Depends(require_active_user), db=Depends(get_db)):
    scoped_tenant_id = _resolve_tenant_id(token_data, tenant_id)
    line = db.get(PreloadLine, line_id)
    if not line or str(line.tenant_id) != scoped_tenant_id:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "preload line not found", "line_id": line_id})
    for field in ("sale_price", "epc", "pool", "location_code", "vendible", "observation", "image_mode", "image_asset_id"):
        value = getattr(payload, field)
        if value is not None:
            setattr(line, field, value)
    line.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(line)
    return _preload_line_response(line)


def _raise_epc_conflict(epc: str, assignment: EpcAssignment, item: StockItem | None) -> None:
    assigned_item = {"item_uid": str(assignment.item_uid)}
    if item is not None:
        assigned_item.update(
            {
                "sku": item.sku,
                "description": item.description,
                "store_id": str(item.store_id) if item.store_id else None,
                "item_status": item.item_status or item.status,
            }
        )
    raise AppError(
        ErrorCatalog.BUSINESS_CONFLICT,
        details={
            "message": "epc already active on another in-stock item",
            "epc": epc,
            "assigned_item": assigned_item,
        },
    )


def _raise_epc_conflict_from_stock(epc: str, item: StockItem) -> None:
    raise AppError(
        ErrorCatalog.BUSINESS_CONFLICT,
        details={
            "message": "epc already active on another in-stock item",
            "epc": epc,
            "assigned_item": {
                "item_uid": str(item.item_uid),
                "sku": item.sku,
                "description": item.description,
                "store_id": str(item.store_id) if item.store_id else None,
                "item_status": item.item_status or item.status,
            },
        },
    )




def _stock_item_for_assignment(db, *, tenant_id: str | UUID, item_uid: str | UUID) -> StockItem | None:
    return db.execute(
        select(StockItem).where(
            StockItem.tenant_id == tenant_id,
            cast(StockItem.item_uid, String) == str(item_uid),
        )
    ).scalar_one_or_none()


def _assert_epc_available(db, *, tenant_id: str | UUID, epc: str):
    assignment = db.execute(
        select(EpcAssignment).where(
            EpcAssignment.tenant_id == tenant_id,
            EpcAssignment.epc == epc,
            EpcAssignment.active.is_(True),
        )
    ).scalar_one_or_none()
    if assignment is not None:
        item = _stock_item_for_assignment(db, tenant_id=assignment.tenant_id, item_uid=assignment.item_uid)
        _raise_epc_conflict(epc, assignment, item)

    stock_match = db.execute(
        select(StockItem).where(
            StockItem.tenant_id == tenant_id,
            StockItem.epc == epc,
            StockItem.item_status == "ACTIVE",
        )
    ).scalar_one_or_none()
    if stock_match is not None:
        _raise_epc_conflict_from_stock(epc, stock_match)


def _commit_preload_epc_write(db, *, tenant_id: UUID, epc: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        assignment = db.execute(
            select(EpcAssignment).where(
                EpcAssignment.tenant_id == tenant_id,
                EpcAssignment.epc == epc,
                EpcAssignment.active.is_(True),
            )
        ).scalar_one_or_none()
        if assignment is not None:
            item = _stock_item_for_assignment(db, tenant_id=assignment.tenant_id, item_uid=assignment.item_uid)
            _raise_epc_conflict(epc, assignment, item)
        stock_match = db.execute(
            select(StockItem).where(
                StockItem.tenant_id == tenant_id,
                StockItem.epc == epc,
                StockItem.item_status == "ACTIVE",
            )
        ).scalar_one_or_none()
        if stock_match is not None:
            _raise_epc_conflict_from_stock(epc, stock_match)
        if _is_epc_conflict_integrity_error(exc):
            raise AppError(
                ErrorCatalog.BUSINESS_CONFLICT,
                details={
                    "message": "epc already active on another in-stock item",
                    "epc": epc,
                    "assigned_item": None,
                },
            ) from exc
        raise


def _is_epc_conflict_integrity_error(exc: IntegrityError) -> bool:
    constraint_name = getattr(getattr(getattr(exc, "orig", None), "diag", None), "constraint_name", None)
    if constraint_name in {"uq_stock_items_tenant_epc", "uq_epc_assignments_active_epc"}:
        return True
    message = str(getattr(exc, "orig", exc)).lower()
    return "uq_stock_items_tenant_epc" in message or "uq_epc_assignments_active_epc" in message


@router.post(
    "/aris3/stock/preload-lines/{line_id}/save",
    response_model=PreloadLineResponse,
    responses={
        409: {
            "model": ApiErrorResponse,
            "description": "BUSINESS_CONFLICT when EPC is already assigned to another active in-stock item.",
        }
    },
)
def save_preload_line(line_id: str, tenant_id: str | None = None, token_data=Depends(get_current_token_data), _user=Depends(require_active_user), db=Depends(get_db)):
    scoped_tenant_id = _resolve_tenant_id(token_data, tenant_id)
    line = db.get(PreloadLine, line_id)
    if not line or str(line.tenant_id) != scoped_tenant_id:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "preload line not found", "line_id": line_id})
    if line.sale_price is None or line.sale_price <= 0:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "sale_price is required and must be greater than 0"})

    now = datetime.utcnow()
    line_tenant_id = line.tenant_id
    if not line.epc:
        stock = StockItem(tenant_id=line_tenant_id, store_id=line.store_id, item_uid=line.item_uid, sku=line.sku, description=line.description, var1_value=line.var1_value, var2_value=line.var2_value, epc=None, location_code=line.location_code, pool=line.pool, status="PENDING", item_status="PENDING_EPC", epc_status="AVAILABLE", observation=line.observation, print_status="NOT_REQUESTED", location_is_vendible=line.vendible, cost_price=line.cost_price, suggested_price=line.suggested_price, sale_price=line.sale_price, image_asset_id=line.image_asset_id, created_at=now, updated_at=now)
        db.add(stock)
        db.flush()
        line.lifecycle_state = "PENDING_EPC"
        line.item_status = "PENDING_EPC"
        line.saved_stock_item_id = stock.id
    else:
        _assert_epc_available(db, tenant_id=line_tenant_id, epc=line.epc)
        stock = StockItem(tenant_id=line_tenant_id, store_id=line.store_id, item_uid=line.item_uid, sku=line.sku, description=line.description, var1_value=line.var1_value, var2_value=line.var2_value, epc=line.epc, location_code=line.location_code, pool=line.pool, status="RFID", item_status="ACTIVE", epc_status="ASSIGNED", observation=line.observation, print_status="READY_TO_PRINT", location_is_vendible=line.vendible, cost_price=line.cost_price, suggested_price=line.suggested_price, sale_price=line.sale_price, image_asset_id=line.image_asset_id, created_at=now, updated_at=now)
        db.add(stock)
        db.flush()
        db.add(EpcAssignment(tenant_id=line_tenant_id, store_id=line.store_id, epc=line.epc, item_uid=line.item_uid, assigned_at=now, active=True, status="ASSIGNED", created_at=now, updated_at=now))
        line.lifecycle_state = "SAVED_EPC_FINAL"
        line.item_status = "ACTIVE"
        line.epc_status = "ASSIGNED"
        line.saved_stock_item_id = stock.id
    line.updated_at = now
    if line.epc:
        _commit_preload_epc_write(db, tenant_id=line.tenant_id, epc=line.epc)
    else:
        db.commit()
    db.refresh(line)
    return _preload_line_response(line)


@router.get("/aris3/stock/pending-epc", response_model=list[PreloadLineResponse])
def list_pending_epc(tenant_id: str | None = None, token_data=Depends(get_current_token_data), _user=Depends(require_active_user), db=Depends(get_db)):
    scoped_tenant_id = _resolve_tenant_id(token_data, tenant_id)
    rows = db.execute(select(PreloadLine).where(PreloadLine.tenant_id == scoped_tenant_id, PreloadLine.lifecycle_state == "PENDING_EPC")).scalars().all()
    return [_preload_line_response(row) for row in rows]


@router.post(
    "/aris3/stock/pending-epc/{line_id}/assign-epc",
    response_model=PreloadLineResponse,
    responses={
        409: {
            "model": ApiErrorResponse,
            "description": "BUSINESS_CONFLICT when EPC is already assigned to another active in-stock item.",
        }
    },
)
def assign_pending_epc(line_id: str, payload: PendingEpcAssignRequest, tenant_id: str | None = None, token_data=Depends(get_current_token_data), _user=Depends(require_active_user), db=Depends(get_db)):
    scoped_tenant_id = _resolve_tenant_id(token_data, tenant_id)
    line = db.get(PreloadLine, line_id)
    if not line or str(line.tenant_id) != scoped_tenant_id:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "preload line not found", "line_id": line_id})
    if line.lifecycle_state != "PENDING_EPC" or not line.saved_stock_item_id:
        raise AppError(
            ErrorCatalog.BUSINESS_CONFLICT,
            details={
                "message": "line must be saved in pending EPC state before assignment",
                "line_id": line_id,
                "lifecycle_state": line.lifecycle_state,
            },
        )
    _assert_epc_available(db, tenant_id=line.tenant_id, epc=payload.epc)
    now = datetime.utcnow()
    line.epc = payload.epc
    line.epc_status = "ASSIGNED"
    line.item_status = "ACTIVE"
    line.lifecycle_state = "SAVED_EPC_FINAL"
    stock = db.get(StockItem, line.saved_stock_item_id) if line.saved_stock_item_id else None
    if stock:
        stock.epc = payload.epc
        stock.status = "RFID"
        stock.item_status = "ACTIVE"
        stock.epc_status = "ASSIGNED"
        stock.updated_at = now
    db.add(EpcAssignment(tenant_id=line.tenant_id, store_id=line.store_id, epc=payload.epc, item_uid=line.item_uid, assigned_at=now, active=True, status="ASSIGNED", created_at=now, updated_at=now))
    line.updated_at = now
    _commit_preload_epc_write(db, tenant_id=line.tenant_id, epc=payload.epc)
    return _preload_line_response(line)


@router.get("/aris3/stock/epc/{epc}/history", response_model=EpcAssignmentHistoryResponse)
def epc_history(epc: str, tenant_id: str | None = None, token_data=Depends(get_current_token_data), _user=Depends(require_active_user), db=Depends(get_db)):
    scoped_tenant_id = _resolve_tenant_id(token_data, tenant_id)
    rows = db.execute(select(EpcAssignment).where(EpcAssignment.tenant_id == scoped_tenant_id, EpcAssignment.epc == epc).order_by(EpcAssignment.assigned_at.desc())).scalars().all()
    current = next((r for r in rows if r.active), None)
    return EpcAssignmentHistoryResponse(epc=epc, current=None if current is None else {"item_uid": str(current.item_uid), "assigned_at": current.assigned_at, "status": current.status}, history=[{"item_uid": str(r.item_uid), "assigned_at": r.assigned_at, "released_at": r.released_at, "active": r.active, "last_release_reason": r.last_release_reason, "status": r.status} for r in rows])


@router.post(
    "/aris3/stock/epc/release",
    response_model=EpcReleaseResponse,
    responses={
        409: {
            "model": ApiErrorResponse,
            "description": "BUSINESS_CONFLICT for invalid EPC release attempts.",
        }
    },
)
def release_epc(payload: EpcReleaseRequest, tenant_id: str | None = None, token_data=Depends(get_current_token_data), _user=Depends(require_active_user), db=Depends(get_db)):
    scoped_tenant_id = _resolve_tenant_id(token_data, tenant_id)
    assignment = db.execute(select(EpcAssignment).where(EpcAssignment.tenant_id == scoped_tenant_id, EpcAssignment.epc == payload.epc, EpcAssignment.item_uid == payload.item_uid, EpcAssignment.active.is_(True))).scalars().first()
    if not assignment:
        raise AppError(
            ErrorCatalog.BUSINESS_CONFLICT,
            details={"message": "invalid EPC release attempt: active assignment not found", "epc": payload.epc},
        )
    assignment.active = False
    assignment.released_at = datetime.utcnow()
    assignment.last_release_reason = payload.reason
    assignment.status = "RELEASED"
    assignment.updated_at = datetime.utcnow()
    stock_item = db.execute(select(StockItem).where(StockItem.tenant_id == scoped_tenant_id, cast(StockItem.item_uid, String) == str(payload.item_uid))).scalars().first()
    if stock_item:
        stock_item.epc_status = "AVAILABLE"
        stock_item.epc = None
        stock_item.updated_at = datetime.utcnow()
    db.commit()
    return {"released": True, "epc": payload.epc, "item_uid": payload.item_uid, "reason": payload.reason}


@router.get("/aris3/catalog/sku/{sku}/images", response_model=list[SkuImageResponse])
def list_sku_images(sku: str, tenant_id: str | None = None, token_data=Depends(get_current_token_data), _user=Depends(require_active_user), db=Depends(get_db)):
    scoped_tenant_id = _resolve_tenant_id(token_data, tenant_id)
    rows = db.execute(select(SkuImage).where(SkuImage.tenant_id == scoped_tenant_id, SkuImage.sku == sku).order_by(SkuImage.is_primary.desc(), SkuImage.sort_order.asc())).scalars().all()
    return [SkuImageResponse(id=str(r.id), tenant_id=str(r.tenant_id), sku=r.sku, asset_id=str(r.asset_id), file_hash=r.file_hash, is_primary=r.is_primary, sort_order=r.sort_order, created_at=r.created_at, updated_at=r.updated_at) for r in rows]


@router.post(
    "/aris3/catalog/sku/{sku}/images",
    response_model=list[SkuImageResponse],
    status_code=201,
    openapi_extra={"parameters": [_IDEMPOTENCY_HEADER_PARAMETER]},
)
def upsert_sku_images(sku: str, payload: SkuImageUpsertRequest, tenant_id: str | None = None, token_data=Depends(get_current_token_data), _user=Depends(require_active_user), db=Depends(get_db)):
    scoped_tenant_id = _resolve_tenant_id(token_data, tenant_id)
    now = datetime.utcnow()
    if payload.mode == "blank":
        return list_sku_images(sku, scoped_tenant_id, token_data, _user, db)  # type: ignore[arg-type]
    if payload.file_hash:
        existing_hash = db.execute(select(SkuImage).where(SkuImage.tenant_id == scoped_tenant_id, SkuImage.sku == sku, SkuImage.file_hash == payload.file_hash)).scalars().first()
        if existing_hash:
            return list_sku_images(sku, scoped_tenant_id, token_data, _user, db)  # type: ignore[arg-type]
    if payload.mode == "replace":
        for row in db.execute(select(SkuImage).where(SkuImage.tenant_id == scoped_tenant_id, SkuImage.sku == sku)).scalars().all():
            row.is_primary = False
            row.updated_at = now
    max_order = db.execute(select(SkuImage.sort_order).where(SkuImage.tenant_id == scoped_tenant_id, SkuImage.sku == sku).order_by(SkuImage.sort_order.desc())).scalars().first() or 0
    db.add(SkuImage(tenant_id=scoped_tenant_id, sku=sku, asset_id=payload.asset_id, file_hash=payload.file_hash, is_primary=payload.mode in {"replace", "use_existing"}, sort_order=max_order + 1, created_at=now, updated_at=now))
    db.commit()
    return list_sku_images(sku, scoped_tenant_id, token_data, _user, db)  # type: ignore[arg-type]


@router.put(
    "/aris3/catalog/sku/{sku}/images/{asset_id}/primary",
    response_model=list[SkuImageResponse],
    openapi_extra={"parameters": [_IDEMPOTENCY_HEADER_PARAMETER]},
)
def set_primary_sku_image(sku: str, asset_id: str, tenant_id: str | None = None, token_data=Depends(get_current_token_data), _user=Depends(require_active_user), db=Depends(get_db)):
    scoped_tenant_id = _resolve_tenant_id(token_data, tenant_id)
    rows = db.execute(select(SkuImage).where(SkuImage.tenant_id == scoped_tenant_id, SkuImage.sku == sku)).scalars().all()
    for row in rows:
        row.is_primary = str(row.asset_id) == asset_id
        row.updated_at = datetime.utcnow()
    db.commit()
    return list_sku_images(sku, scoped_tenant_id, token_data, _user, db)  # type: ignore[arg-type]


@router.post(
    "/aris3/stock/items/{item_uid}/mark-issue",
    response_model=ItemIssueResponse,
    responses={
        409: {
            "model": ApiErrorResponse,
            "description": "BUSINESS_CONFLICT for invalid issue/disposition state transitions.",
        }
    },
)
def mark_issue(item_uid: str, payload: ItemIssueRequest, tenant_id: str | None = None, token_data=Depends(get_current_token_data), _user=Depends(require_active_user), db=Depends(get_db)):
    scoped_tenant_id = _resolve_tenant_id(token_data, tenant_id)
    item = db.execute(select(StockItem).where(StockItem.tenant_id == scoped_tenant_id, cast(StockItem.item_uid, String) == item_uid)).scalars().first()
    if not item:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "item not found", "item_uid": item_uid})
    if item.item_status == "SOLD":
        raise AppError(
            ErrorCatalog.BUSINESS_CONFLICT,
            details={"message": "invalid state transition: sold items cannot be marked with issue disposition", "item_uid": item_uid},
        )
    item.issue_state = payload.issue_state
    item.item_status = payload.issue_state
    item.observation = payload.observation
    item.updated_at = datetime.utcnow()
    if payload.release_epc and item.epc:
        assignment = db.execute(select(EpcAssignment).where(EpcAssignment.tenant_id == scoped_tenant_id, EpcAssignment.epc == item.epc, EpcAssignment.item_uid == item.item_uid, EpcAssignment.active.is_(True))).scalars().first()
        if assignment:
            assignment.active = False
            assignment.released_at = datetime.utcnow()
            assignment.last_release_reason = payload.release_reason or payload.issue_state
            assignment.status = "RELEASED"
            assignment.updated_at = datetime.utcnow()
        item.epc_status = "AVAILABLE"
        if not payload.keep_epc_assigned:
            item.epc = None
            item.status = "PENDING"
    db.commit()
    return {"item_uid": item_uid, "item_status": item.item_status, "issue_state": item.issue_state, "epc_status": item.epc_status}


@router.post(
    "/aris3/stock/items/{item_uid}/resolve-issue",
    response_model=ItemIssueResolveResponse,
    responses={
        409: {
            "model": ApiErrorResponse,
            "description": "BUSINESS_CONFLICT for invalid issue/disposition state transitions.",
        }
    },
)
def resolve_issue(item_uid: str, payload: ItemIssueResolveRequest, tenant_id: str | None = None, token_data=Depends(get_current_token_data), _user=Depends(require_active_user), db=Depends(get_db)):
    scoped_tenant_id = _resolve_tenant_id(token_data, tenant_id)
    item = db.execute(select(StockItem).where(StockItem.tenant_id == scoped_tenant_id, cast(StockItem.item_uid, String) == item_uid)).scalars().first()
    if not item:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "item not found", "item_uid": item_uid})
    if not item.issue_state:
        raise AppError(
            ErrorCatalog.BUSINESS_CONFLICT,
            details={"message": "invalid state transition: item is not currently in issue state", "item_uid": item_uid},
        )
    item.item_status = payload.item_status
    if payload.item_status == "ACTIVE":
        item.status = "RFID"
    item.issue_state = None
    item.observation = payload.observation
    item.updated_at = datetime.utcnow()
    db.commit()
    return {"item_uid": item_uid, "item_status": item.item_status, "issue_state": item.issue_state}
