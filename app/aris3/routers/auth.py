from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.core.deps import require_active_user
from app.aris3.db.session import get_db
from app.aris3.repos.users import UserRepository
from app.aris3.schemas.auth import ChangePasswordRequest, ChangePasswordResponse, LoginRequest, TokenResponse
from app.aris3.services.audit import AuditEventPayload, AuditService
from app.aris3.services.auth import AuthService
from app.aris3.services.idempotency import (
    IdempotencyService,
    extract_idempotency_key,
)

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(request: Request, payload: LoginRequest, db=Depends(get_db)):
    service = AuthService(db)
    repo = UserRepository(db)
    identifier = payload.email or payload.username_or_email
    idempotency_key = extract_idempotency_key(request.headers, required=False)

    try:
        user, token = service.login(identifier, payload.password)
    except AppError as exc:
        candidates = repo.list_by_username_or_email(identifier)
        if candidates:
            candidate = candidates[0]
            audit = AuditService(db)
            audit.record_event(
                AuditEventPayload(
                    tenant_id=str(candidate.tenant_id),
                    user_id=str(candidate.id),
                    store_id=str(candidate.store_id) if candidate.store_id else None,
                    trace_id=getattr(request.state, "trace_id", None),
                    actor=identifier,
                    action="auth.login.failed",
                    entity_type="user",
                    entity_id=str(candidate.id),
                    before=None,
                    after=None,
                    metadata={"error_code": exc.error.code},
                    result="failure",
                )
            )
        raise

    if idempotency_key:
        request_hash = IdempotencyService.fingerprint(payload.model_dump(mode="json"))
        idempotency_service = IdempotencyService(db)
        context, replay = idempotency_service.start(
            tenant_id=str(user.tenant_id),
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

    response = TokenResponse(access_token=token, must_change_password=user.must_change_password)

    if idempotency_key:
        context = getattr(request.state, "idempotency", None)
        if context is not None:
            context.record_success(status_code=200, response_body=response.model_dump())

    audit = AuditService(db)
    audit.record_event(
        AuditEventPayload(
            tenant_id=str(user.tenant_id),
            user_id=str(user.id),
            store_id=str(user.store_id) if user.store_id else None,
            trace_id=getattr(request.state, "trace_id", None),
            actor=user.username,
            action="auth.login",
            entity_type="user",
            entity_id=str(user.id),
            before=None,
            after=None,
            metadata=None,
            result="success",
        )
    )
    return response


@router.post("/change-password", response_model=ChangePasswordResponse)
async def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    idempotency_key = extract_idempotency_key(request.headers, required=True)
    request_hash = IdempotencyService.fingerprint(payload.model_dump(mode="json"))
    idempotency_service = IdempotencyService(db)
    context, replay = idempotency_service.start(
        tenant_id=str(current_user.tenant_id),
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

    service = AuthService(db)
    try:
        user, token = service.change_password(current_user, payload.current_password, payload.new_password)
    except AppError as exc:
        audit = AuditService(db)
        audit.record_event(
            AuditEventPayload(
                tenant_id=str(current_user.tenant_id),
                user_id=str(current_user.id),
                store_id=str(current_user.store_id) if current_user.store_id else None,
                trace_id=getattr(request.state, "trace_id", None),
                actor=current_user.username,
                action="auth.change_password.failed",
                entity_type="user",
                entity_id=str(current_user.id),
                before=None,
                after=None,
                metadata={"error_code": exc.error.code},
                result="failure",
            )
        )
        raise

    response = ChangePasswordResponse(access_token=token, must_change_password=user.must_change_password)
    context.record_success(status_code=200, response_body=response.model_dump())

    audit = AuditService(db)
    audit.record_event(
        AuditEventPayload(
            tenant_id=str(user.tenant_id),
            user_id=str(user.id),
            store_id=str(user.store_id) if user.store_id else None,
            trace_id=getattr(request.state, "trace_id", None),
            actor=user.username,
            action="auth.change_password",
            entity_type="user",
            entity_id=str(user.id),
            before=None,
            after={"must_change_password": user.must_change_password},
            metadata=None,
            result="success",
        )
    )
    return response
