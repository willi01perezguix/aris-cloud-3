from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.core.deps import require_active_user
from app.aris3.db.session import get_db
from app.aris3.repos.users import UserRepository
from app.aris3.schemas.auth import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    LoginRequest,
    OAuth2TokenResponse,
    TokenResponse,
)
from app.aris3.services.audit import AuditEventPayload, AuditService
from app.aris3.services.auth import AuthService
from app.aris3.services.idempotency import (
    IdempotencyService,
    extract_idempotency_key,
)

router = APIRouter()


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login (JSON)",
    description="Login for JSON clients (UI/admin/scripts) using email or username_or_email.",
)
async def login(request: Request, payload: LoginRequest, db=Depends(get_db)):
    service = AuthService(db)
    repo = UserRepository(db)
    identifier = payload.email or payload.username_or_email
    idempotency_key = extract_idempotency_key(request.headers, required=False)
    trace_id = getattr(request.state, "trace_id", "")

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
                    trace_id=trace_id or None,
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

    response = TokenResponse(
        access_token=token,
        must_change_password=user.must_change_password,
        trace_id=trace_id,
    )

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
            trace_id=trace_id or None,
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


@router.post(
    "/token",
    response_model=OAuth2TokenResponse,
    summary="OAuth2 Token (Swagger/Auth)",
    description="OAuth2 Password Flow endpoint for Swagger Authorize using form-data username/password.",
)
async def oauth2_token(
    request: Request,
    db=Depends(get_db),
):
    raw_body = (await request.body()).decode()
    form_data = parse_qs(raw_body)
    username = (form_data.get("username") or [""])[0]
    password = (form_data.get("password") or [""])[0]

    service = AuthService(db)
    _, token = service.login(username, password)
    return OAuth2TokenResponse(access_token=token)


@router.post(
    "/change-password",
    response_model=ChangePasswordResponse,
    summary="Change Password (Authenticated User)",
)
@router.patch(
    "/change-password",
    response_model=ChangePasswordResponse,
    summary="Change Password (Authenticated User)",
)
async def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    trace_id = getattr(request.state, "trace_id", "")
    idempotency_key = extract_idempotency_key(request.headers, required=False)
    context = None
    if idempotency_key:
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
        user = service.change_password(current_user, payload.current_password, payload.new_password)
    except AppError as exc:
        audit = AuditService(db)
        audit.record_event(
            AuditEventPayload(
                tenant_id=str(current_user.tenant_id),
                user_id=str(current_user.id),
                store_id=str(current_user.store_id) if current_user.store_id else None,
                trace_id=trace_id or None,
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

    response = ChangePasswordResponse(
        ok=True,
        message="Password updated successfully",
        trace_id=trace_id,
    )
    if context is not None:
        context.record_success(status_code=200, response_body=response.model_dump())

    audit = AuditService(db)
    audit.record_event(
        AuditEventPayload(
            tenant_id=str(user.tenant_id),
            user_id=str(user.id),
            store_id=str(user.store_id) if user.store_id else None,
            trace_id=trace_id or None,
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
