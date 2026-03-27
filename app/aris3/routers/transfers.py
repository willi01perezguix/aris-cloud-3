from __future__ import annotations

from decimal import Decimal
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import and_, delete, or_, select

from app.aris3.core.deps import get_current_token_data, require_active_user, require_any_permission
from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.core.context import get_request_context
from app.aris3.core.scope import is_superadmin
from app.aris3.db.models import StockItem, Store, Transfer, TransferLine, TransferMovement
from app.aris3.db.session import get_db
from app.aris3.repos.transfers import TransferQueryFilters, TransferRepository
from app.aris3.schemas.transfers import (
    TransferActionRequest,
    TransferCreateRequest,
    TransferLineCreate,
    TransferLineResponse,
    TransferLineSnapshot,
    TransferListMeta,
    TransferListResponse,
    TransferResponse,
    TransferStoreListResponse,
    TransferStoreResponse,
    TransferUpdateRequest,
)
from app.aris3.services.access_control import AccessControlService
from app.aris3.services.audit import AuditEventPayload, AuditService
from app.aris3.services.idempotency import IdempotencyService, extract_idempotency_key


router = APIRouter()
_IN_TRANSIT_CODE = "IN_TRANSIT"
_DEFAULT_RECEIVE_POOL = "SALE"
_BROAD_ACCESS_ROLES = {"SUPERADMIN", "PLATFORM_ADMIN", "ADMIN"}
_ACTIVE_TRANSFER_STATUSES = {"DRAFT", "DISPATCHED", "PARTIAL_RECEIVED"}


def _normalized_role(token_data) -> str:
    return (getattr(token_data, "role", None) or "").upper()


def _has_broad_transfer_scope(token_data) -> bool:
    return _normalized_role(token_data) in _BROAD_ACCESS_ROLES


def _enforce_origin_store_scope(token_data, origin_store_id: str) -> None:
    if _has_broad_transfer_scope(token_data):
        return
    if not token_data.store_id or str(token_data.store_id) != str(origin_store_id):
        raise AppError(
            ErrorCatalog.STORE_SCOPE_MISMATCH,
            details={"message": "origin store is outside user scope", "origin_store_id": origin_store_id},
        )


def _enforce_destination_store_scope(token_data, destination_store_id: str) -> None:
    if _has_broad_transfer_scope(token_data):
        return
    if not token_data.store_id or str(token_data.store_id) != str(destination_store_id):
        raise AppError(
            ErrorCatalog.STORE_SCOPE_MISMATCH,
            details={"message": "destination store is outside user scope", "destination_store_id": destination_store_id},
        )


def _is_visible_transfer(token_data, transfer: Transfer) -> bool:
    if _has_broad_transfer_scope(token_data):
        return True
    user_store_id = str(token_data.store_id) if token_data.store_id else None
    if not user_store_id:
        return False
    return user_store_id in {str(transfer.origin_store_id), str(transfer.destination_store_id)}


def _stock_snapshot_from_item(item: StockItem) -> dict:
    return {
        "sku": item.sku,
        "description": item.description,
        "var1_value": item.var1_value,
        "var2_value": item.var2_value,
        "cost_price": item.cost_price,
        "suggested_price": item.suggested_price,
        "sale_price": item.sale_price,
        "epc": item.epc,
        "location_code": item.location_code,
        "pool": item.pool,
        "status": item.status,
        "location_is_vendible": item.location_is_vendible,
        "image_asset_id": item.image_asset_id,
        "image_url": item.image_url,
        "image_thumb_url": item.image_thumb_url,
        "image_source": item.image_source,
        "image_updated_at": item.image_updated_at,
    }


def _active_transfer_line_exists(db, *, tenant_id: str, line: TransferLineCreate, exclude_transfer_id: str | None = None) -> bool:
    conditions = [
        TransferLine.tenant_id == tenant_id,
        Transfer.id == TransferLine.transfer_id,
        Transfer.tenant_id == tenant_id,
        Transfer.status.in_(_ACTIVE_TRANSFER_STATUSES),
    ]
    if exclude_transfer_id:
        conditions.append(Transfer.id != exclude_transfer_id)
    if line.line_type == "EPC":
        conditions.append(TransferLine.epc == line.snapshot.epc)
    else:
        conditions.extend(
            [
                TransferLine.sku == line.snapshot.sku,
                TransferLine.description == line.snapshot.description,
                TransferLine.var1_value == line.snapshot.var1_value,
                TransferLine.var2_value == line.snapshot.var2_value,
                TransferLine.location_code == line.snapshot.location_code,
                TransferLine.pool == line.snapshot.pool,
                TransferLine.status == line.snapshot.status,
            ]
        )
    query = select(TransferLine.id).join(Transfer, Transfer.id == TransferLine.transfer_id).where(and_(*conditions)).limit(1)
    return db.execute(query).scalars().first() is not None




def _validate_transferable_epc_stock(
    db,
    *,
    tenant_id: str,
    origin_store_id: str,
    epc: str,
    expected_location_code: str | None = None,
    expected_pool: str | None = None,
):
    stock_row = (
        db.execute(
            select(StockItem)
            .where(
                StockItem.tenant_id == tenant_id,
                or_(StockItem.store_id == origin_store_id, StockItem.store_id.is_(None)),
                StockItem.epc == epc,
            )
            .with_for_update()
        )
        .scalars()
        .first()
    )
    if not stock_row:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={
                "message": "epc is not available in origin_store_id",
                "epc": epc,
                "origin_store_id": origin_store_id,
            },
        )

    if stock_row.status != "RFID":
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "stock is not transferable", "epc": epc, "status": stock_row.status},
        )

    if stock_row.location_code == _IN_TRANSIT_CODE or stock_row.pool == _IN_TRANSIT_CODE:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "stock is already in transit", "epc": epc},
        )

    if expected_location_code and stock_row.location_code != expected_location_code:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={
                "message": "stock location changed since draft snapshot",
                "epc": epc,
                "expected_location_code": expected_location_code,
                "actual_location_code": stock_row.location_code,
            },
        )

    if expected_pool and stock_row.pool != expected_pool:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={
                "message": "stock pool changed since draft snapshot",
                "epc": epc,
                "expected_pool": expected_pool,
                "actual_pool": stock_row.pool,
            },
        )

    return stock_row


def _normalize_transfer_line(db, *, tenant_id: str, origin_store_id: str, line: TransferLineCreate, exclude_transfer_id: str | None = None) -> dict:
    _validate_transfer_snapshot(line)
    if line.line_type != "EPC":
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "Transfers currently support EPC/RFID lines only"},
        )
    if line.snapshot.status == "PENDING":
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "PENDING stock is not transferable"})

    stock_row = _validate_transferable_epc_stock(
        db,
        tenant_id=tenant_id,
        origin_store_id=origin_store_id,
        epc=line.snapshot.epc,
    )

    if _active_transfer_line_exists(db, tenant_id=tenant_id, line=line, exclude_transfer_id=exclude_transfer_id):
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "stock is already committed in an active transfer"})

    snapshot = _stock_snapshot_from_item(stock_row)
    return {"line_type": line.line_type, "qty": line.qty, "snapshot": snapshot}


def _normalize_transfer_lines(db, *, tenant_id: str, origin_store_id: str, lines: list[TransferLineCreate], exclude_transfer_id: str | None = None) -> list[dict]:
    normalized: list[dict] = []
    for line in lines:
        normalized.append(
            _normalize_transfer_line(
                db,
                tenant_id=tenant_id,
                origin_store_id=origin_store_id,
                line=line,
                exclude_transfer_id=exclude_transfer_id,
            )
        )
    return normalized


def _revalidate_existing_draft_lines(
    db,
    *,
    tenant_id: str,
    origin_store_id: str,
    lines: list[TransferLine],
    transfer_id: str,
) -> None:
    for line in lines:
        if line.line_type != "EPC":
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "Transfers currently support EPC/RFID lines only"},
            )
        if not line.epc:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "epc is required for EPC lines"},
            )
        _validate_transferable_epc_stock(
            db,
            tenant_id=tenant_id,
            origin_store_id=origin_store_id,
            epc=line.epc,
            expected_location_code=line.location_code,
            expected_pool=line.pool,
        )
        as_create_line = TransferLineCreate(
            line_type="EPC",
            qty=line.qty,
            snapshot=TransferLineSnapshot(
                sku=line.sku,
                description=line.description,
                var1_value=line.var1_value,
                var2_value=line.var2_value,
                cost_price=float(line.cost_price) if line.cost_price is not None else None,
                suggested_price=float(line.suggested_price) if line.suggested_price is not None else None,
                sale_price=float(line.sale_price) if line.sale_price is not None else None,
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
            ),
        )
        if _active_transfer_line_exists(
            db,
            tenant_id=tenant_id,
            line=as_create_line,
            exclude_transfer_id=transfer_id,
        ):
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "stock is already committed in an active transfer", "epc": line.epc},
            )



def _resolve_tenant_id(token_data, tenant_id: str | None) -> str:
    if not token_data.tenant_id:
        raise AppError(ErrorCatalog.TENANT_SCOPE_REQUIRED)
    if tenant_id and tenant_id != token_data.tenant_id:
        raise AppError(ErrorCatalog.CROSS_TENANT_ACCESS_DENIED)
    return token_data.tenant_id


def _visible_store_ids(token_data) -> set[str] | None:
    if _has_broad_transfer_scope(token_data):
        return None
    if not token_data.store_id:
        return set()
    return {str(token_data.store_id)}


def _resolve_tenant_id_from_request(token_data, tenant_id: str | None) -> str:
    return _resolve_tenant_id(token_data, tenant_id)


def _require_action_permission(request: Request, db, permission_key: str, token_data) -> None:
    context = get_request_context(request)
    cache = getattr(request.state, "permission_cache", None)
    if cache is None:
        cache = {}
        request.state.permission_cache = cache
    service = AccessControlService(db, cache=cache)
    for key in (permission_key, "TRANSFER_MANAGE"):
        decision = service.evaluate_permission(key, context, token_data)
        if decision.allowed:
            return
    raise AppError(ErrorCatalog.PERMISSION_DENIED)


def _require_transaction_id(transaction_id: str | None) -> None:
    if not transaction_id:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "transaction_id is required"},
        )


def _normalize_uuid(value: str | UUID) -> str:
    return str(value)


def _validate_transfer_snapshot(line: TransferLineCreate) -> None:
    snapshot = line.snapshot
    if line.qty < 1:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "qty must be at least 1", "qty": line.qty},
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
    if not snapshot.location_code or not snapshot.pool:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "location_code and pool are required in line snapshot"},
        )


def _ensure_store_tenant(db, tenant_id: str, store_id: str, *, field_name: str) -> None:
    exists = (
        db.execute(select(Store.id).where(Store.id == store_id, Store.tenant_id == tenant_id))
        .scalars()
        .first()
    )
    if not exists:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": f"{field_name} must belong to tenant_id", field_name: store_id},
        )


def _require_destination_user(current_user, transfer: Transfer) -> None:
    if not current_user.store_id or str(current_user.store_id) != str(transfer.destination_store_id):
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "only destination store users can perform this action"},
        )


def _resolve_receive_destination(receive_line, transfer: Transfer) -> tuple[str, str, bool]:
    location_code = receive_line.location_code or f"STORE-{transfer.destination_store_id}"
    pool = receive_line.pool or _DEFAULT_RECEIVE_POOL
    location_is_vendible = True if receive_line.location_is_vendible is None else receive_line.location_is_vendible
    return location_code, pool, location_is_vendible


def _stock_snapshot_from_line(line: TransferLine) -> dict:
    def _to_json_number(value):
        if value is None:
            return None
        if isinstance(value, Decimal):
            return float(value)
        return value

    image_updated_at = line.image_updated_at
    if isinstance(image_updated_at, datetime):
        image_updated_at = image_updated_at.isoformat()
    return {
        "sku": line.sku,
        "description": line.description,
        "var1_value": line.var1_value,
        "var2_value": line.var2_value,
        "cost_price": _to_json_number(line.cost_price),
        "suggested_price": _to_json_number(line.suggested_price),
        "sale_price": _to_json_number(line.sale_price),
        "epc": line.epc,
        "location_code": line.location_code,
        "pool": line.pool,
        "status": line.status,
        "location_is_vendible": line.location_is_vendible,
        "image_asset_id": str(line.image_asset_id) if line.image_asset_id else None,
        "image_url": line.image_url,
        "image_thumb_url": line.image_thumb_url,
        "image_source": line.image_source,
        "image_updated_at": image_updated_at,
    }


def _line_status_from_totals(line: TransferLine, totals: dict[str, int]) -> dict[str, int | str]:
    dispatched_qty = totals.get("DISPATCH", 0)
    received_qty = totals.get("RECEIVE", 0)
    lost_qty = totals.get("SHORTAGE_RESOLVED_LOST_IN_ROUTE", 0)
    shortage_reported = totals.get("SHORTAGE_REPORTED", 0)
    shortage_resolved_found = totals.get("SHORTAGE_RESOLVED_FOUND_AND_RESEND", 0)
    shortage_resolved_lost = totals.get("SHORTAGE_RESOLVED_LOST_IN_ROUTE", 0)

    baseline_qty = dispatched_qty if dispatched_qty > 0 else line.qty
    outstanding_qty = max(baseline_qty - received_qty - lost_qty, 0)
    shortage_remaining = max(shortage_reported - shortage_resolved_found - shortage_resolved_lost, 0)

    if shortage_reported == 0:
        shortage_status = "NONE"
    elif shortage_remaining > 0:
        shortage_status = "REPORTED"
    else:
        shortage_status = "RESOLVED"

    if shortage_resolved_found or shortage_resolved_lost:
        if shortage_remaining == 0 and shortage_reported > 0:
            if shortage_resolved_found and shortage_resolved_lost:
                resolution_status = "MIXED"
            elif shortage_resolved_found:
                resolution_status = "FOUND_AND_RESEND"
            else:
                resolution_status = "LOST_IN_ROUTE"
        else:
            resolution_status = "PARTIAL"
    else:
        resolution_status = "NONE"

    return {
        "received_qty": received_qty,
        "outstanding_qty": outstanding_qty,
        "shortage_status": shortage_status,
        "resolution_status": resolution_status,
    }


def _transfer_line_response(line: TransferLine, movement_totals: dict[str, dict[str, int]]) -> TransferLineResponse:
    totals = movement_totals.get(_normalize_uuid(line.id), {})
    status = _line_status_from_totals(line, totals)
    snapshot = TransferLineSnapshot(
        sku=line.sku,
        description=line.description,
        var1_value=line.var1_value,
        var2_value=line.var2_value,
        cost_price=line.cost_price,
        suggested_price=line.suggested_price,
        sale_price=line.sale_price,
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
    return TransferLineResponse(
        id=_normalize_uuid(line.id),
        line_type=line.line_type,
        qty=line.qty,
        received_qty=int(status["received_qty"]),
        outstanding_qty=int(status["outstanding_qty"]),
        shortage_status=str(status["shortage_status"]),
        resolution_status=str(status["resolution_status"]),
        snapshot=snapshot,
        created_at=line.created_at,
    )


def _movement_summary(
    repo: TransferRepository,
    transfer: Transfer,
    movement_totals: dict[str, dict[str, int]],
) -> dict:
    dispatched_lines, dispatched_qty = repo.count_dispatched(_normalize_uuid(transfer.id))
    outstanding_total = 0
    for totals in movement_totals.values():
        dispatched = totals.get("DISPATCH", 0)
        received = totals.get("RECEIVE", 0)
        lost = totals.get("SHORTAGE_RESOLVED_LOST_IN_ROUTE", 0)
        outstanding_total += max(dispatched - received - lost, 0)
    pending_reception = outstanding_total > 0 and transfer.status in {"DISPATCHED", "PARTIAL_RECEIVED"}
    return {
        "dispatched_lines": dispatched_lines,
        "dispatched_qty": dispatched_qty,
        "pending_reception": pending_reception,
        "shortages_possible": pending_reception,
    }


def _transfer_response(repo: TransferRepository, transfer: Transfer, lines: list[TransferLine]) -> TransferResponse:
    movement_totals = repo.get_movement_totals(_normalize_uuid(transfer.id))
    header = {
        "id": _normalize_uuid(transfer.id),
        "tenant_id": _normalize_uuid(transfer.tenant_id),
        "origin_store_id": _normalize_uuid(transfer.origin_store_id),
        "destination_store_id": _normalize_uuid(transfer.destination_store_id),
        "status": transfer.status,
        "created_by_user_id": _normalize_uuid(transfer.created_by_user_id) if transfer.created_by_user_id else None,
        "updated_by_user_id": _normalize_uuid(transfer.updated_by_user_id) if transfer.updated_by_user_id else None,
        "dispatched_by_user_id": _normalize_uuid(transfer.dispatched_by_user_id)
        if transfer.dispatched_by_user_id
        else None,
        "canceled_by_user_id": _normalize_uuid(transfer.canceled_by_user_id) if transfer.canceled_by_user_id else None,
        "dispatched_at": transfer.dispatched_at,
        "canceled_at": transfer.canceled_at,
        "received_at": transfer.received_at,
        "created_at": transfer.created_at,
        "updated_at": transfer.updated_at,
    }
    return TransferResponse(
        header=header,
        lines=[_transfer_line_response(line, movement_totals) for line in lines],
        movement_summary=_movement_summary(repo, transfer, movement_totals),
    )


@router.get("/aris3/transfers", response_model=TransferListResponse)
def list_transfers(
    status: str | None = Query(default=None),
    origin_store_id: str | None = Query(default=None),
    destination_store_id: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None, deprecated=True),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort_by: str = Query(default="created_at"),
    sort_dir: str = Query(default="desc"),
    token_data=Depends(get_current_token_data),
    _user=Depends(require_active_user),
    _permission=Depends(require_any_permission(("transfers.read", "TRANSFER_VIEW"))),
    db=Depends(get_db),
):
    scoped_tenant_id = _resolve_tenant_id(token_data, tenant_id)
    visible_store_ids = _visible_store_ids(token_data)
    if sort_by not in {"created_at", "updated_at"}:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "invalid sort_by"})
    if sort_dir not in {"asc", "desc"}:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "invalid sort_dir"})

    repo = TransferRepository(db)
    rows, total = repo.list_transfers(
        TransferQueryFilters(
            tenant_id=scoped_tenant_id,
            status=status,
            origin_store_id=origin_store_id,
            destination_store_id=destination_store_id,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_dir=sort_dir,
            visible_store_ids=visible_store_ids,
        )
    )
    responses = []
    for transfer in rows:
        lines = repo.get_lines(_normalize_uuid(transfer.id))
        responses.append(_transfer_response(repo, transfer, lines))
    response = TransferListResponse(rows=responses)
    response_dict = response.model_dump(mode="json")
    response_dict["meta"] = TransferListMeta(page=page, page_size=page_size, total=total).model_dump(mode="json")
    return JSONResponse(content=response_dict)


@router.get("/aris3/stores", response_model=TransferStoreListResponse)
def list_tenant_stores(
    token_data=Depends(get_current_token_data),
    _user=Depends(require_active_user),
    _permission=Depends(require_any_permission(("transfers.read", "TRANSFER_VIEW"))),
    db=Depends(get_db),
):
    scoped_tenant_id = _resolve_tenant_id(token_data, token_data.tenant_id)
    visible_store_ids = _visible_store_ids(token_data)
    query = select(Store).where(Store.tenant_id == scoped_tenant_id)
    if visible_store_ids is not None:
        if not visible_store_ids:
            return TransferStoreListResponse(rows=[])
        query = query.where(Store.id.in_(visible_store_ids))
    rows = db.execute(query.order_by(Store.name.asc())).scalars().all()
    return TransferStoreListResponse(
        rows=[TransferStoreResponse(id=_normalize_uuid(row.id), code=row.name, name=row.name, active=True) for row in rows]
    )


@router.post("/aris3/transfers", response_model=TransferResponse, status_code=201)
def create_transfer(
    request: Request,
    payload: TransferCreateRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    _permission=Depends(require_any_permission(("transfers.create", "TRANSFER_MANAGE"))),
    db=Depends(get_db),
):
    _require_transaction_id(payload.transaction_id)
    scoped_tenant_id = _resolve_tenant_id_from_request(token_data, payload.tenant_id)
    if payload.origin_store_id == payload.destination_store_id:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "origin_store_id and destination_store_id must differ"},
        )
    _ensure_store_tenant(db, scoped_tenant_id, payload.origin_store_id, field_name="origin_store_id")
    _ensure_store_tenant(db, scoped_tenant_id, payload.destination_store_id, field_name="destination_store_id")
    _enforce_origin_store_scope(token_data, payload.origin_store_id)
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

    normalized_lines = _normalize_transfer_lines(
        db,
        tenant_id=scoped_tenant_id,
        origin_store_id=payload.origin_store_id,
        lines=payload.lines,
    )

    transfer = Transfer(
        tenant_id=scoped_tenant_id,
        origin_store_id=payload.origin_store_id,
        destination_store_id=payload.destination_store_id,
        status="DRAFT",
        created_by_user_id=current_user.id,
        updated_by_user_id=current_user.id,
    )
    db.add(transfer)
    db.flush()

    lines = []
    for line in normalized_lines:
        snapshot = line["snapshot"]
        lines.append(
            TransferLine(
                transfer_id=transfer.id,
                tenant_id=scoped_tenant_id,
                line_type=line["line_type"],
                qty=line["qty"],
                sku=snapshot["sku"],
                description=snapshot["description"],
                var1_value=snapshot["var1_value"],
                var2_value=snapshot["var2_value"],
                cost_price=snapshot["cost_price"],
                suggested_price=snapshot["suggested_price"],
                sale_price=snapshot["sale_price"],
                epc=snapshot["epc"],
                location_code=snapshot["location_code"],
                pool=snapshot["pool"],
                status=snapshot["status"],
                location_is_vendible=snapshot["location_is_vendible"],
                image_asset_id=snapshot["image_asset_id"],
                image_url=snapshot["image_url"],
                image_thumb_url=snapshot["image_thumb_url"],
                image_source=snapshot["image_source"],
                image_updated_at=snapshot["image_updated_at"],
            )
        )
    db.add_all(lines)
    db.commit()

    repo = TransferRepository(db)
    response = _transfer_response(repo, transfer, lines)
    context.record_success(status_code=201, response_body=response.model_dump(mode="json"))
    AuditService(db).record_event(
        AuditEventPayload(
            tenant_id=scoped_tenant_id,
            user_id=str(current_user.id),
            store_id=str(current_user.store_id) if current_user.store_id else None,
            trace_id=getattr(request.state, "trace_id", "") or None,
            actor=current_user.username,
            action="transfer.create",
            entity_type="transfer",
            entity_id=_normalize_uuid(transfer.id),
            before=None,
            after=response.model_dump(mode="json"),
            metadata={"transaction_id": payload.transaction_id},
            result="success",
        )
    )
    return response


@router.patch("/aris3/transfers/{transfer_id}", response_model=TransferResponse)
def update_transfer(
    transfer_id: str,
    request: Request,
    payload: TransferUpdateRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    _permission=Depends(require_any_permission(("transfers.update", "TRANSFER_MANAGE"))),
    db=Depends(get_db),
):
    _require_transaction_id(payload.transaction_id)
    scoped_tenant_id = _resolve_tenant_id_from_request(token_data, payload.tenant_id)
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

    repo = TransferRepository(db)
    transfer = (
        db.execute(
            select(Transfer)
            .where(Transfer.id == transfer_id, Transfer.tenant_id == scoped_tenant_id)
            .with_for_update()
        )
        .scalars()
        .first()
    )
    if not transfer:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "transfer not found"})
    if transfer.status != "DRAFT":
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "only draft transfers can be updated"},
        )

    current_origin_store_id = str(payload.origin_store_id or transfer.origin_store_id)
    current_destination_store_id = str(payload.destination_store_id or transfer.destination_store_id)
    if current_origin_store_id == current_destination_store_id:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "origin_store_id and destination_store_id must differ"},
        )

    _ensure_store_tenant(db, scoped_tenant_id, current_origin_store_id, field_name="origin_store_id")
    _ensure_store_tenant(db, scoped_tenant_id, current_destination_store_id, field_name="destination_store_id")
    _enforce_origin_store_scope(token_data, current_origin_store_id)

    transfer.origin_store_id = current_origin_store_id
    transfer.destination_store_id = current_destination_store_id

    if payload.lines is not None:
        if not payload.lines:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "lines must not be empty"},
            )
        normalized_lines = _normalize_transfer_lines(
            db,
            tenant_id=scoped_tenant_id,
            origin_store_id=current_origin_store_id,
            lines=payload.lines,
            exclude_transfer_id=transfer_id,
        )
        db.execute(delete(TransferLine).where(TransferLine.transfer_id == transfer.id))
        new_lines = []
        for line in normalized_lines:
            snapshot = line["snapshot"]
            new_lines.append(
                TransferLine(
                    transfer_id=transfer.id,
                    tenant_id=scoped_tenant_id,
                    line_type=line["line_type"],
                    qty=line["qty"],
                    sku=snapshot["sku"],
                    description=snapshot["description"],
                    var1_value=snapshot["var1_value"],
                    var2_value=snapshot["var2_value"],
                    cost_price=snapshot["cost_price"],
                    suggested_price=snapshot["suggested_price"],
                    sale_price=snapshot["sale_price"],
                    epc=snapshot["epc"],
                    location_code=snapshot["location_code"],
                    pool=snapshot["pool"],
                    status=snapshot["status"],
                    location_is_vendible=snapshot["location_is_vendible"],
                    image_asset_id=snapshot["image_asset_id"],
                    image_url=snapshot["image_url"],
                    image_thumb_url=snapshot["image_thumb_url"],
                    image_source=snapshot["image_source"],
                    image_updated_at=snapshot["image_updated_at"],
                )
            )
        db.add_all(new_lines)
    else:
        existing_lines = repo.get_lines(_normalize_uuid(transfer.id))
        _revalidate_existing_draft_lines(
            db,
            tenant_id=scoped_tenant_id,
            origin_store_id=current_origin_store_id,
            lines=existing_lines,
            transfer_id=_normalize_uuid(transfer.id),
        )
    transfer.updated_by_user_id = current_user.id
    transfer.updated_at = datetime.utcnow()
    db.commit()

    lines = repo.get_lines(_normalize_uuid(transfer.id))
    response = _transfer_response(repo, transfer, lines)
    context.record_success(status_code=200, response_body=response.model_dump(mode="json"))
    AuditService(db).record_event(
        AuditEventPayload(
            tenant_id=scoped_tenant_id,
            user_id=str(current_user.id),
            store_id=str(current_user.store_id) if current_user.store_id else None,
            trace_id=getattr(request.state, "trace_id", "") or None,
            actor=current_user.username,
            action="transfer.update",
            entity_type="transfer",
            entity_id=_normalize_uuid(transfer.id),
            before=None,
            after=response.model_dump(mode="json"),
            metadata={"transaction_id": payload.transaction_id},
            result="success",
        )
    )
    return response


@router.get("/aris3/transfers/{transfer_id}", response_model=TransferResponse)
def get_transfer_detail(
    transfer_id: str,
    token_data=Depends(get_current_token_data),
    _user=Depends(require_active_user),
    _permission=Depends(require_any_permission(("transfers.read", "TRANSFER_VIEW"))),
    db=Depends(get_db),
):
    scoped_tenant_id = _resolve_tenant_id(token_data, token_data.tenant_id)
    repo = TransferRepository(db)
    transfer = repo.get_transfer(transfer_id, scoped_tenant_id)
    if not transfer or not _is_visible_transfer(token_data, transfer):
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "transfer not found"})
    lines = repo.get_lines(transfer_id)
    return _transfer_response(repo, transfer, lines)


@router.post("/aris3/transfers/{transfer_id}/actions", response_model=TransferResponse)
def transfer_actions(
    transfer_id: str,
    request: Request,
    payload: TransferActionRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    _permission=Depends(require_any_permission(("transfers.dispatch", "transfers.receive", "transfers.cancel", "transfers.resolve", "TRANSFER_MANAGE"))),
    db=Depends(get_db),
):
    _require_transaction_id(payload.transaction_id)
    scoped_tenant_id = _resolve_tenant_id_from_request(token_data, payload.tenant_id)
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

    repo = TransferRepository(db)
    transfer = (
        db.execute(
            select(Transfer)
            .where(Transfer.id == transfer_id, Transfer.tenant_id == scoped_tenant_id)
            .with_for_update()
        )
        .scalars()
        .first()
    )
    if not transfer:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "transfer not found"})

    action = payload.action
    if action == "dispatch":
        _require_action_permission(request, db, "transfers.dispatch", token_data)
        _enforce_origin_store_scope(token_data, str(transfer.origin_store_id))
        if transfer.status != "DRAFT":
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "only draft transfers can be dispatched"},
            )
        lines = repo.get_lines(transfer_id)
        if not lines:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "transfer has no lines"},
            )
        movements = []
        for line in lines:
            if line.line_type != "EPC":
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "Transfers currently support EPC/RFID lines only"},
                )
            if not line.epc:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "epc is required for EPC dispatch"},
                )
            row = _validate_transferable_epc_stock(
                db,
                tenant_id=scoped_tenant_id,
                origin_store_id=str(transfer.origin_store_id),
                epc=line.epc,
                expected_location_code=line.location_code,
                expected_pool=line.pool,
            )
            row.location_code = _IN_TRANSIT_CODE
            row.pool = _IN_TRANSIT_CODE
            row.store_id = transfer.origin_store_id
            row.location_is_vendible = False
            row.updated_at = datetime.utcnow()
            movements.append(
                TransferMovement(
                    tenant_id=scoped_tenant_id,
                    transfer_id=transfer.id,
                    transfer_line_id=line.id,
                    action="DISPATCH",
                    from_location_code=line.location_code,
                    from_pool=line.pool,
                    to_location_code=_IN_TRANSIT_CODE,
                    to_pool=_IN_TRANSIT_CODE,
                    status=line.status,
                    qty=1,
                    snapshot=_stock_snapshot_from_line(line),
                )
            )
        db.add_all(movements)
        transfer.status = "DISPATCHED"
        transfer.dispatched_by_user_id = current_user.id
        transfer.dispatched_at = datetime.utcnow()
        transfer.updated_at = datetime.utcnow()
        transfer.updated_by_user_id = current_user.id
        db.commit()
        lines = repo.get_lines(transfer_id)
        response = _transfer_response(repo, transfer, lines)
        context.record_success(status_code=200, response_body=response.model_dump(mode="json"))
        AuditService(db).record_event(
            AuditEventPayload(
                tenant_id=scoped_tenant_id,
                user_id=str(current_user.id),
                store_id=str(current_user.store_id) if current_user.store_id else None,
                trace_id=getattr(request.state, "trace_id", "") or None,
                actor=current_user.username,
                action="transfer.dispatch",
                entity_type="transfer",
                entity_id=_normalize_uuid(transfer.id),
                before=None,
                after=response.model_dump(mode="json"),
                metadata={"transaction_id": payload.transaction_id},
                result="success",
            )
        )
        return response

    if action == "receive":
        _require_action_permission(request, db, "transfers.receive", token_data)
        _enforce_destination_store_scope(token_data, str(transfer.destination_store_id))
        if transfer.status not in {"DISPATCHED", "PARTIAL_RECEIVED"}:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "transfer cannot be received from this state"},
            )
        if not payload.receive_lines:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "receive_lines must not be empty"},
            )
        lines = repo.get_lines(transfer_id)
        line_map = {_normalize_uuid(line.id): line for line in lines}
        movement_totals = repo.get_movement_totals(transfer_id)
        movements: list[TransferMovement] = []

        for receive_line in payload.receive_lines:
            line = line_map.get(receive_line.line_id)
            if not line:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "transfer line not found", "line_id": receive_line.line_id},
                )
            if receive_line.qty < 1:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "receive qty must be at least 1", "line_id": receive_line.line_id},
                )
            totals = movement_totals.get(receive_line.line_id, {})
            dispatched = totals.get("DISPATCH", 0)
            received = totals.get("RECEIVE", 0)
            lost = totals.get("SHORTAGE_RESOLVED_LOST_IN_ROUTE", 0)
            outstanding = dispatched - received - lost
            if receive_line.qty > outstanding:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "receive qty exceeds outstanding", "line_id": receive_line.line_id},
                )
            target_location_code, target_pool, target_is_vendible = _resolve_receive_destination(receive_line, transfer)
            if line.line_type != "EPC":
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "Transfers currently support EPC/RFID lines only"},
                )
            if receive_line.qty != 1:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "receive qty must be 1 for EPC lines", "line_id": receive_line.line_id},
                )
            if not line.epc:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "epc is required for EPC receive", "line_id": receive_line.line_id},
                )
            row = (
                db.execute(
                    select(StockItem)
                    .where(
                        StockItem.tenant_id == scoped_tenant_id,
                        StockItem.epc == line.epc,
                        or_(StockItem.store_id == transfer.origin_store_id, StockItem.store_id.is_(None)),
                        StockItem.location_code == _IN_TRANSIT_CODE,
                        StockItem.pool == _IN_TRANSIT_CODE,
                    )
                    .with_for_update()
                )
                .scalars()
                .first()
            )
            if not row:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "epc item not in transit", "epc": line.epc},
                )
            row.location_code = target_location_code
            row.pool = target_pool
            row.store_id = transfer.destination_store_id
            row.location_is_vendible = target_is_vendible
            row.updated_at = datetime.utcnow()

            movements.append(
                TransferMovement(
                    tenant_id=scoped_tenant_id,
                    transfer_id=transfer.id,
                    transfer_line_id=line.id,
                    action="RECEIVE",
                    from_location_code=_IN_TRANSIT_CODE,
                    from_pool=_IN_TRANSIT_CODE,
                    to_location_code=target_location_code,
                    to_pool=target_pool,
                    status=line.status,
                    qty=receive_line.qty,
                    snapshot={
                        "line_snapshot": _stock_snapshot_from_line(line),
                        "received_location_code": target_location_code,
                        "received_pool": target_pool,
                        "received_location_is_vendible": target_is_vendible,
                    },
                )
            )

        db.add_all(movements)
        for receive_line in payload.receive_lines:
            totals = movement_totals.get(receive_line.line_id, {})
            totals["RECEIVE"] = totals.get("RECEIVE", 0) + receive_line.qty
            movement_totals[receive_line.line_id] = totals

        outstanding_total = 0
        for totals in movement_totals.values():
            dispatched = totals.get("DISPATCH", 0)
            received = totals.get("RECEIVE", 0)
            lost = totals.get("SHORTAGE_RESOLVED_LOST_IN_ROUTE", 0)
            outstanding_total += max(dispatched - received - lost, 0)
        if outstanding_total == 0:
            transfer.status = "RECEIVED"
            transfer.received_at = datetime.utcnow()
        else:
            transfer.status = "PARTIAL_RECEIVED"
        transfer.updated_at = datetime.utcnow()
        transfer.updated_by_user_id = current_user.id
        db.commit()
        lines = repo.get_lines(transfer_id)
        response = _transfer_response(repo, transfer, lines)
        context.record_success(status_code=200, response_body=response.model_dump(mode="json"))
        AuditService(db).record_event(
            AuditEventPayload(
                tenant_id=scoped_tenant_id,
                user_id=str(current_user.id),
                store_id=str(current_user.store_id) if current_user.store_id else None,
                trace_id=getattr(request.state, "trace_id", "") or None,
                actor=current_user.username,
                action="transfer.receive",
                entity_type="transfer",
                entity_id=_normalize_uuid(transfer.id),
                before=None,
                after=response.model_dump(mode="json"),
                metadata={"transaction_id": payload.transaction_id},
                result="success",
            )
        )
        return response

    if action == "report_shortages":
        _require_action_permission(request, db, "transfers.resolve", token_data)
        _enforce_destination_store_scope(token_data, str(transfer.destination_store_id))
        if transfer.status not in {"DISPATCHED", "PARTIAL_RECEIVED"}:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "shortages cannot be reported from this state"},
            )
        if not payload.shortages:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "shortages must not be empty"},
            )
        lines = repo.get_lines(transfer_id)
        line_map = {_normalize_uuid(line.id): line for line in lines}
        movement_totals = repo.get_movement_totals(transfer_id)
        movements = []

        outstanding_total = 0
        for totals in movement_totals.values():
            dispatched = totals.get("DISPATCH", 0)
            received = totals.get("RECEIVE", 0)
            lost = totals.get("SHORTAGE_RESOLVED_LOST_IN_ROUTE", 0)
            outstanding_total += max(dispatched - received - lost, 0)
        if outstanding_total <= 0:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "no outstanding quantities to report shortages"},
            )

        for shortage in payload.shortages:
            line = line_map.get(shortage.line_id)
            if not line:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "transfer line not found", "line_id": shortage.line_id},
                )
            if shortage.qty < 1:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "shortage qty must be at least 1", "line_id": shortage.line_id},
                )
            if line.line_type == "EPC" and shortage.qty != 1:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "shortage qty must be 1 for EPC lines", "line_id": shortage.line_id},
                )
            totals = movement_totals.get(shortage.line_id, {})
            dispatched = totals.get("DISPATCH", 0)
            received = totals.get("RECEIVE", 0)
            lost = totals.get("SHORTAGE_RESOLVED_LOST_IN_ROUTE", 0)
            reported = totals.get("SHORTAGE_REPORTED", 0)
            if shortage.qty + reported > max(dispatched - received - lost, 0):
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "shortage qty exceeds outstanding", "line_id": shortage.line_id},
                )
            movements.append(
                TransferMovement(
                    tenant_id=scoped_tenant_id,
                    transfer_id=transfer.id,
                    transfer_line_id=line.id,
                    action="SHORTAGE_REPORTED",
                    from_location_code=_IN_TRANSIT_CODE,
                    from_pool=_IN_TRANSIT_CODE,
                    to_location_code=_IN_TRANSIT_CODE,
                    to_pool=_IN_TRANSIT_CODE,
                    status=line.status,
                    qty=shortage.qty,
                    snapshot={
                        "line_snapshot": _stock_snapshot_from_line(line),
                        "reason_code": shortage.reason_code,
                        "notes": shortage.notes,
                    },
                )
            )
        db.add_all(movements)
        transfer.updated_at = datetime.utcnow()
        transfer.updated_by_user_id = current_user.id
        db.commit()
        lines = repo.get_lines(transfer_id)
        response = _transfer_response(repo, transfer, lines)
        context.record_success(status_code=200, response_body=response.model_dump(mode="json"))
        AuditService(db).record_event(
            AuditEventPayload(
                tenant_id=scoped_tenant_id,
                user_id=str(current_user.id),
                store_id=str(current_user.store_id) if current_user.store_id else None,
                trace_id=getattr(request.state, "trace_id", "") or None,
                actor=current_user.username,
                action="transfer.shortages.report",
                entity_type="transfer",
                entity_id=_normalize_uuid(transfer.id),
                before=None,
                after=response.model_dump(mode="json"),
                metadata={"transaction_id": payload.transaction_id},
                result="success",
            )
        )
        return response

    if action == "resolve_shortages":
        _require_action_permission(request, db, "transfers.resolve", token_data)
        _enforce_destination_store_scope(token_data, str(transfer.destination_store_id))
        if transfer.status not in {"DISPATCHED", "PARTIAL_RECEIVED"}:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "shortages cannot be resolved from this state"},
            )
        if not payload.resolution or not payload.resolution.lines:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "resolution lines must not be empty"},
            )
        resolution_type = payload.resolution.resolution
        if resolution_type == "LOST_IN_ROUTE":
            if not is_superadmin(token_data.role) and token_data.role not in {"MANAGER", "ADMIN"}:
                raise AppError(ErrorCatalog.PERMISSION_DENIED)

        lines = repo.get_lines(transfer_id)
        line_map = {_normalize_uuid(line.id): line for line in lines}
        movement_totals = repo.get_movement_totals(transfer_id)
        movements = []

        for resolution_line in payload.resolution.lines:
            line = line_map.get(resolution_line.line_id)
            if not line:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "transfer line not found", "line_id": resolution_line.line_id},
                )
            if resolution_line.qty < 1:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "resolution qty must be at least 1", "line_id": resolution_line.line_id},
                )
            if line.line_type == "EPC" and resolution_line.qty != 1:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={
                        "message": "resolution qty must be 1 for EPC lines",
                        "line_id": resolution_line.line_id,
                    },
                )
            totals = movement_totals.get(resolution_line.line_id, {})
            reported = totals.get("SHORTAGE_REPORTED", 0)
            resolved_found = totals.get("SHORTAGE_RESOLVED_FOUND_AND_RESEND", 0)
            resolved_lost = totals.get("SHORTAGE_RESOLVED_LOST_IN_ROUTE", 0)
            shortage_remaining = max(reported - resolved_found - resolved_lost, 0)
            if resolution_line.qty > shortage_remaining:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "resolution qty exceeds shortage remaining", "line_id": resolution_line.line_id},
                )

            if resolution_type == "FOUND_AND_RESEND":
                movements.append(
                    TransferMovement(
                        tenant_id=scoped_tenant_id,
                        transfer_id=transfer.id,
                        transfer_line_id=line.id,
                        action="SHORTAGE_RESOLVED_FOUND_AND_RESEND",
                        from_location_code=line.location_code,
                        from_pool=line.pool,
                        to_location_code=_IN_TRANSIT_CODE,
                        to_pool=_IN_TRANSIT_CODE,
                        status=line.status,
                        qty=resolution_line.qty,
                        snapshot={
                            "line_snapshot": _stock_snapshot_from_line(line),
                            "resolution": resolution_type,
                        },
                    )
                )
            else:
                if line.line_type == "EPC":
                    row = (
                        db.execute(
                            select(StockItem)
                            .where(
                                StockItem.tenant_id == scoped_tenant_id,
                                StockItem.epc == line.epc,
                                StockItem.location_code == _IN_TRANSIT_CODE,
                                StockItem.pool == _IN_TRANSIT_CODE,
                            )
                            .with_for_update()
                        )
                        .scalars()
                        .first()
                    )
                    if not row:
                        raise AppError(
                            ErrorCatalog.VALIDATION_ERROR,
                            details={"message": "epc item not in transit", "epc": line.epc},
                        )
                    db.delete(row)
                else:
                    pending_rows = (
                        db.execute(
                            select(StockItem)
                            .where(
                                StockItem.tenant_id == scoped_tenant_id,
                                or_(StockItem.store_id == transfer.origin_store_id, StockItem.store_id.is_(None)),
                            StockItem.sku == line.sku,
                                StockItem.description == line.description,
                                StockItem.var1_value == line.var1_value,
                                StockItem.var2_value == line.var2_value,
                                StockItem.epc.is_(None),
                                StockItem.location_code == _IN_TRANSIT_CODE,
                                StockItem.pool == _IN_TRANSIT_CODE,
                                StockItem.status == line.status,
                            StockItem.status != "PENDING",
                            )
                            .with_for_update()
                            .order_by(StockItem.created_at.asc())
                            .limit(resolution_line.qty)
                        )
                        .scalars()
                        .all()
                    )
                    if len(pending_rows) < resolution_line.qty:
                        raise AppError(
                            ErrorCatalog.VALIDATION_ERROR,
                            details={
                                "message": "insufficient in-transit stock for loss",
                                "line_id": resolution_line.line_id,
                            },
                        )
                    for row in pending_rows:
                        db.delete(row)

                movements.append(
                    TransferMovement(
                        tenant_id=scoped_tenant_id,
                        transfer_id=transfer.id,
                        transfer_line_id=line.id,
                        action="SHORTAGE_RESOLVED_LOST_IN_ROUTE",
                        from_location_code=_IN_TRANSIT_CODE,
                        from_pool=_IN_TRANSIT_CODE,
                        to_location_code="LOST_IN_ROUTE",
                        to_pool="LOST_IN_ROUTE",
                        status=line.status,
                        qty=resolution_line.qty,
                        snapshot={
                            "line_snapshot": _stock_snapshot_from_line(line),
                            "resolution": resolution_type,
                        },
                    )
                )

        db.add_all(movements)
        for resolution_line in payload.resolution.lines:
            totals = movement_totals.get(resolution_line.line_id, {})
            if resolution_type == "FOUND_AND_RESEND":
                totals["SHORTAGE_RESOLVED_FOUND_AND_RESEND"] = totals.get(
                    "SHORTAGE_RESOLVED_FOUND_AND_RESEND", 0
                ) + resolution_line.qty
            else:
                totals["SHORTAGE_RESOLVED_LOST_IN_ROUTE"] = totals.get(
                    "SHORTAGE_RESOLVED_LOST_IN_ROUTE", 0
                ) + resolution_line.qty
            movement_totals[resolution_line.line_id] = totals

        outstanding_total = 0
        for totals in movement_totals.values():
            dispatched = totals.get("DISPATCH", 0)
            received = totals.get("RECEIVE", 0)
            lost = totals.get("SHORTAGE_RESOLVED_LOST_IN_ROUTE", 0)
            outstanding_total += max(dispatched - received - lost, 0)
        if outstanding_total == 0 and transfer.status in {"DISPATCHED", "PARTIAL_RECEIVED"}:
            transfer.status = "RECEIVED"
            transfer.received_at = datetime.utcnow()
        transfer.updated_at = datetime.utcnow()
        transfer.updated_by_user_id = current_user.id
        db.commit()
        lines = repo.get_lines(transfer_id)
        response = _transfer_response(repo, transfer, lines)
        context.record_success(status_code=200, response_body=response.model_dump(mode="json"))
        AuditService(db).record_event(
            AuditEventPayload(
                tenant_id=scoped_tenant_id,
                user_id=str(current_user.id),
                store_id=str(current_user.store_id) if current_user.store_id else None,
                trace_id=getattr(request.state, "trace_id", "") or None,
                actor=current_user.username,
                action="transfer.shortages.resolve",
                entity_type="transfer",
                entity_id=_normalize_uuid(transfer.id),
                before=None,
                after=response.model_dump(mode="json"),
                metadata={"transaction_id": payload.transaction_id, "resolution": resolution_type},
                result="success",
            )
        )
        return response

    if action == "cancel":
        _require_action_permission(request, db, "transfers.cancel", token_data)
        if transfer.status == "DISPATCHED" and transfer.received_at is not None:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "dispatched transfers with receptions cannot be cancelled"},
            )
        if transfer.status not in {"DRAFT", "DISPATCHED"}:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "transfer cannot be cancelled from this state"},
            )
        transfer.status = "CANCELLED"
        transfer.canceled_by_user_id = current_user.id
        transfer.canceled_at = datetime.utcnow()
        transfer.updated_at = datetime.utcnow()
        transfer.updated_by_user_id = current_user.id
        db.commit()
        lines = repo.get_lines(transfer_id)
        response = _transfer_response(repo, transfer, lines)
        context.record_success(status_code=200, response_body=response.model_dump(mode="json"))
        AuditService(db).record_event(
            AuditEventPayload(
                tenant_id=scoped_tenant_id,
                user_id=str(current_user.id),
                store_id=str(current_user.store_id) if current_user.store_id else None,
                trace_id=getattr(request.state, "trace_id", "") or None,
                actor=current_user.username,
                action="transfer.cancel",
                entity_type="transfer",
                entity_id=_normalize_uuid(transfer.id),
                before=None,
                after=response.model_dump(mode="json"),
                metadata={"transaction_id": payload.transaction_id},
                result="success",
            )
        )
        return response

    raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "unsupported action"})
