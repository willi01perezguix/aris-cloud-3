from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import delete
from sqlalchemy import select

from app.aris3.core.deps import get_current_token_data, require_active_user, require_permission
from app.aris3.core.error_catalog import AppError, ErrorCatalog
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
    TransferListResponse,
    TransferResponse,
    TransferUpdateRequest,
)
from app.aris3.services.audit import AuditEventPayload, AuditService
from app.aris3.services.idempotency import IdempotencyService, extract_idempotency_key


router = APIRouter()
_IN_TRANSIT_CODE = "IN_TRANSIT"
_DEFAULT_RECEIVE_POOL = "SALE"



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


def _resolve_tenant_id_from_request(token_data, tenant_id: str | None) -> str:
    return _resolve_tenant_id(token_data, tenant_id)


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
    image_updated_at = line.image_updated_at
    if isinstance(image_updated_at, datetime):
        image_updated_at = image_updated_at.isoformat()
    return {
        "sku": line.sku,
        "description": line.description,
        "var1_value": line.var1_value,
        "var2_value": line.var2_value,
        "cost_price": line.cost_price,
        "suggested_price": line.suggested_price,
        "sale_price": line.sale_price,
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

    outstanding_qty = max(dispatched_qty - received_qty - lost_qty, 0)
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
    token_data=Depends(get_current_token_data),
    _user=Depends(require_active_user),
    _permission=Depends(require_permission("TRANSFER_VIEW")),
    db=Depends(get_db),
):
    scoped_tenant_id = _resolve_tenant_id(token_data, token_data.tenant_id)
    repo = TransferRepository(db)
    rows = repo.list_transfers(TransferQueryFilters(tenant_id=scoped_tenant_id))
    responses = []
    for transfer in rows:
        lines = repo.get_lines(_normalize_uuid(transfer.id))
        responses.append(_transfer_response(repo, transfer, lines))
    return TransferListResponse(rows=responses)


@router.post("/aris3/transfers", response_model=TransferResponse, status_code=201)
def create_transfer(
    request: Request,
    payload: TransferCreateRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    _permission=Depends(require_permission("TRANSFER_MANAGE")),
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

    for line in payload.lines:
        _validate_transfer_snapshot(line)

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
    for line in payload.lines:
        snapshot = line.snapshot
        lines.append(
            TransferLine(
                transfer_id=transfer.id,
                tenant_id=scoped_tenant_id,
                line_type=line.line_type,
                qty=line.qty,
                sku=snapshot.sku,
                description=snapshot.description,
                var1_value=snapshot.var1_value,
                var2_value=snapshot.var2_value,
                cost_price=snapshot.cost_price,
                suggested_price=snapshot.suggested_price,
                sale_price=snapshot.sale_price,
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
    _permission=Depends(require_permission("TRANSFER_MANAGE")),
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
    transfer = repo.get_transfer(transfer_id, scoped_tenant_id)
    if not transfer:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "transfer not found"})
    if transfer.status != "DRAFT":
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "only draft transfers can be updated"},
        )

    if payload.origin_store_id and payload.destination_store_id:
        if payload.origin_store_id == payload.destination_store_id:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "origin_store_id and destination_store_id must differ"},
            )
    if payload.origin_store_id:
        _ensure_store_tenant(db, scoped_tenant_id, payload.origin_store_id, field_name="origin_store_id")
        transfer.origin_store_id = payload.origin_store_id
    if payload.destination_store_id:
        _ensure_store_tenant(db, scoped_tenant_id, payload.destination_store_id, field_name="destination_store_id")
        transfer.destination_store_id = payload.destination_store_id

    if payload.lines is not None:
        if not payload.lines:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "lines must not be empty"},
            )
        for line in payload.lines:
            _validate_transfer_snapshot(line)
        db.execute(delete(TransferLine).where(TransferLine.transfer_id == transfer.id))
        new_lines = []
        for line in payload.lines:
            snapshot = line.snapshot
            new_lines.append(
                TransferLine(
                    transfer_id=transfer.id,
                    tenant_id=scoped_tenant_id,
                    line_type=line.line_type,
                    qty=line.qty,
                    sku=snapshot.sku,
                    description=snapshot.description,
                    var1_value=snapshot.var1_value,
                    var2_value=snapshot.var2_value,
                    cost_price=snapshot.cost_price,
                    suggested_price=snapshot.suggested_price,
                    sale_price=snapshot.sale_price,
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
        db.add_all(new_lines)
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
    _permission=Depends(require_permission("TRANSFER_VIEW")),
    db=Depends(get_db),
):
    scoped_tenant_id = _resolve_tenant_id(token_data, token_data.tenant_id)
    repo = TransferRepository(db)
    transfer = repo.get_transfer(transfer_id, scoped_tenant_id)
    if not transfer:
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
    _permission=Depends(require_permission("TRANSFER_MANAGE")),
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
            if line.line_type == "EPC":
                if not line.epc:
                    raise AppError(
                        ErrorCatalog.VALIDATION_ERROR,
                        details={"message": "epc is required for EPC dispatch"},
                    )
                row = (
                    db.execute(
                        select(StockItem)
                        .where(
                            StockItem.tenant_id == scoped_tenant_id,
                            StockItem.epc == line.epc,
                            StockItem.location_code == line.location_code,
                            StockItem.pool == line.pool,
                        )
                        .with_for_update()
                    )
                    .scalars()
                    .first()
                )
                if not row:
                    raise AppError(
                        ErrorCatalog.VALIDATION_ERROR,
                        details={"message": "insufficient stock for EPC dispatch", "epc": line.epc},
                    )
                row.location_code = _IN_TRANSIT_CODE
                row.pool = _IN_TRANSIT_CODE
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
            else:
                pending_rows = (
                    db.execute(
                        select(StockItem)
                        .where(
                            StockItem.tenant_id == scoped_tenant_id,
                            StockItem.sku == line.sku,
                            StockItem.description == line.description,
                            StockItem.var1_value == line.var1_value,
                            StockItem.var2_value == line.var2_value,
                            StockItem.epc.is_(None),
                            StockItem.location_code == line.location_code,
                            StockItem.pool == line.pool,
                            StockItem.status == line.status,
                        )
                        .with_for_update()
                        .order_by(StockItem.created_at.asc())
                        .limit(line.qty)
                    )
                    .scalars()
                    .all()
                )
                if len(pending_rows) < line.qty:
                    raise AppError(
                        ErrorCatalog.VALIDATION_ERROR,
                        details={"message": "insufficient stock for SKU dispatch", "sku": line.sku},
                    )
                for row in pending_rows:
                    row.location_code = _IN_TRANSIT_CODE
                    row.pool = _IN_TRANSIT_CODE
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
                        qty=line.qty,
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
        _require_destination_user(current_user, transfer)
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
            if line.line_type == "EPC" and receive_line.qty != 1:
                raise AppError(
                    ErrorCatalog.VALIDATION_ERROR,
                    details={"message": "receive qty must be 1 for EPC lines", "line_id": receive_line.line_id},
                )
            if line.line_type == "EPC":
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
                row.location_is_vendible = target_is_vendible
                row.updated_at = datetime.utcnow()
            else:
                pending_rows = (
                    db.execute(
                        select(StockItem)
                        .where(
                            StockItem.tenant_id == scoped_tenant_id,
                            StockItem.sku == line.sku,
                            StockItem.description == line.description,
                            StockItem.var1_value == line.var1_value,
                            StockItem.var2_value == line.var2_value,
                            StockItem.epc.is_(None),
                            StockItem.location_code == _IN_TRANSIT_CODE,
                            StockItem.pool == _IN_TRANSIT_CODE,
                            StockItem.status == line.status,
                        )
                        .with_for_update()
                        .order_by(StockItem.created_at.asc())
                        .limit(receive_line.qty)
                    )
                    .scalars()
                    .all()
                )
                if len(pending_rows) < receive_line.qty:
                    raise AppError(
                        ErrorCatalog.VALIDATION_ERROR,
                        details={
                            "message": "insufficient in-transit stock for receive",
                            "line_id": receive_line.line_id,
                        },
                    )
                for row in pending_rows:
                    row.location_code = target_location_code
                    row.pool = target_pool
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
        _require_destination_user(current_user, transfer)
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
        _require_destination_user(current_user, transfer)
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
                                StockItem.sku == line.sku,
                                StockItem.description == line.description,
                                StockItem.var1_value == line.var1_value,
                                StockItem.var2_value == line.var2_value,
                                StockItem.epc.is_(None),
                                StockItem.location_code == _IN_TRANSIT_CODE,
                                StockItem.pool == _IN_TRANSIT_CODE,
                                StockItem.status == line.status,
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
