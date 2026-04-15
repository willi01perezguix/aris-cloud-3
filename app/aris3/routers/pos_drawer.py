from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.aris3.core.deps import get_current_token_data, require_active_user, require_permission
from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.core.scope import DEFAULT_BROAD_STORE_ROLES, is_superadmin
from app.aris3.db.models import DrawerEvent
from app.aris3.db.session import get_db
from app.aris3.schemas.errors import ApiErrorResponse, ApiValidationErrorResponse
from app.aris3.schemas.pos_drawer import DrawerEventConfirmCloseRequest, DrawerEventCreateRequest, DrawerEventResponse

router = APIRouter(prefix="/aris3/pos/drawer")

POS_STANDARD_ERROR_RESPONSES = {
    401: {"description": "Unauthorized", "model": ApiErrorResponse},
    403: {"description": "Forbidden", "model": ApiErrorResponse},
    404: {"description": "Resource not found", "model": ApiErrorResponse},
    422: {"description": "Validation error", "model": ApiValidationErrorResponse},
}


def _normalize_uuid(value: str | UUID | None) -> str | None:
    return str(value) if value else None


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


def _event_response(event: DrawerEvent) -> DrawerEventResponse:
    return DrawerEventResponse(
        id=_normalize_uuid(event.id),
        tenant_id=_normalize_uuid(event.tenant_id),
        store_id=_normalize_uuid(event.store_id),
        terminal_id=event.terminal_id,
        user_id=_normalize_uuid(event.user_id),
        cash_session_id=_normalize_uuid(event.cash_session_id),
        sale_id=_normalize_uuid(event.sale_id),
        movement_type=event.movement_type,
        event_type=event.event_type,
        reason=event.reason,
        printer_name=event.printer_name,
        machine_name=event.machine_name,
        requested_at=event.requested_at,
        executed_at=event.executed_at,
        closed_confirmed_at=event.closed_confirmed_at,
        result=event.result,
        details_json=event.details_json,
        trace_id=event.trace_id,
        created_at=event.created_at,
    )


@router.post(
    "/events",
    response_model=DrawerEventResponse,
    responses=POS_STANDARD_ERROR_RESPONSES,
    summary="Record drawer hardware event",
)
def create_drawer_event(
    payload: DrawerEventCreateRequest,
    request: Request,
    db=Depends(get_db),
    token_data: Annotated[object, Depends(get_current_token_data)] = None,
    _active=Depends(require_active_user),
    _permission=Depends(require_permission("POS_CASH_MANAGE")),
):
    tenant_id = _resolve_tenant_id(token_data, payload.tenant_id)
    store_id = _resolve_store_id(token_data, payload.store_id)

    trace_id = payload.trace_id or getattr(request.state, "trace_id", None)
    event = DrawerEvent(
        tenant_id=tenant_id,
        store_id=store_id,
        terminal_id=payload.terminal_id,
        user_id=token_data.sub,
        cash_session_id=payload.cash_session_id,
        sale_id=payload.sale_id,
        movement_type=payload.movement_type,
        event_type=payload.event_type,
        reason=payload.reason,
        printer_name=payload.printer_name,
        machine_name=payload.machine_name,
        requested_at=payload.requested_at,
        executed_at=payload.executed_at,
        closed_confirmed_at=payload.closed_confirmed_at,
        result=payload.result,
        details_json=payload.details_json,
        trace_id=trace_id,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return _event_response(event)


@router.post(
    "/events/{event_id}/actions",
    response_model=DrawerEventResponse,
    responses=POS_STANDARD_ERROR_RESPONSES,
    summary="Execute drawer event action",
)
def drawer_event_action(
    event_id: str,
    payload: DrawerEventConfirmCloseRequest,
    request: Request,
    db=Depends(get_db),
    token_data: Annotated[object, Depends(get_current_token_data)] = None,
    _active=Depends(require_active_user),
    _permission=Depends(require_permission("POS_CASH_MANAGE")),
):
    if payload.action != "CONFIRM_CLOSE":
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "unsupported action", "action": payload.action})

    tenant_id = _resolve_tenant_id(token_data, payload.tenant_id)
    store_id = _resolve_store_id(token_data, payload.store_id)

    event = db.get(DrawerEvent, event_id)
    if not event or _normalize_uuid(event.tenant_id) != tenant_id or _normalize_uuid(event.store_id) != store_id:
        raise AppError(ErrorCatalog.RESOURCE_NOT_FOUND, details={"message": "drawer event not found", "event_id": event_id})

    closed_at = payload.closed_confirmed_at or datetime.utcnow()
    event.closed_confirmed_at = closed_at
    event.trace_id = payload.trace_id or getattr(request.state, "trace_id", None) or event.trace_id
    db.add(event)
    db.commit()
    db.refresh(event)

    confirm_event = DrawerEvent(
        tenant_id=event.tenant_id,
        store_id=event.store_id,
        terminal_id=event.terminal_id,
        user_id=token_data.sub,
        cash_session_id=event.cash_session_id,
        sale_id=event.sale_id,
        movement_type=event.movement_type,
        event_type="DRAWER_CLOSE_CONFIRMED",
        reason="Manual drawer close confirmation",
        printer_name=event.printer_name,
        machine_name=event.machine_name,
        requested_at=closed_at,
        executed_at=closed_at,
        closed_confirmed_at=closed_at,
        result="SUCCESS",
        details_json={"source_event_id": str(event.id)},
        trace_id=event.trace_id,
    )
    db.add(confirm_event)
    db.commit()

    return _event_response(event)
