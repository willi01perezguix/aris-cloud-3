from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.aris3.core.deps import get_current_token_data, require_active_user, require_request_context
from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.core.scope import enforce_tenant_scope, is_superadmin
from app.aris3.db.session import get_db
from app.aris3.repos.users import UserRepository
from app.aris3.schemas.access_control import (
    EffectivePermissionsResponse,
    PermissionCatalogEntry,
    PermissionCatalogResponse,
    PermissionEntry,
    RolePolicyRequest,
    RolePolicyResponse,
    UserPermissionOverrideRequest,
    UserPermissionOverrideResponse,
)
from app.aris3.services.access_control import AccessControlService
from app.aris3.services.access_control_policies import AccessControlPolicyService
from app.aris3.services.audit import AuditEventPayload, AuditService
from app.aris3.services.idempotency import IdempotencyService, extract_idempotency_key

router = APIRouter()


@router.get("/effective-permissions", response_model=EffectivePermissionsResponse)
async def effective_permissions(
    request: Request,
    token_data=Depends(get_current_token_data),
    _current_user=Depends(require_active_user),
    context=Depends(require_request_context),
    db=Depends(get_db),
):
    cache = getattr(request.state, "permission_cache", None)
    if cache is None:
        cache = {}
        request.state.permission_cache = cache
    service = AccessControlService(db, cache=cache)
    decisions = service.build_effective_permissions(context, token_data)
    return EffectivePermissionsResponse(
        user_id=context.user_id or token_data.sub,
        tenant_id=context.tenant_id or token_data.tenant_id,
        store_id=context.store_id or token_data.store_id,
        role=(context.role or token_data.role),
        permissions=[PermissionEntry(key=d.key, allowed=d.allowed, source=d.source) for d in decisions],
        trace_id=getattr(request.state, "trace_id", ""),
    )


@router.get("/permission-catalog", response_model=PermissionCatalogResponse)
async def permission_catalog(
    request: Request,
    token_data=Depends(get_current_token_data),
    _current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    _require_admin(token_data)
    service = AccessControlPolicyService(db)
    permissions = service.list_permission_catalog()
    return PermissionCatalogResponse(
        permissions=[
            PermissionCatalogEntry(code=perm.code, description=perm.description) for perm in permissions
        ],
        trace_id=getattr(request.state, "trace_id", ""),
    )


@router.get("/tenants/{tenant_id}/role-policies/{role_name}", response_model=RolePolicyResponse)
async def get_tenant_role_policy(
    request: Request,
    tenant_id: str,
    role_name: str,
    token_data=Depends(get_current_token_data),
    _current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    _require_admin(token_data)
    enforce_tenant_scope(token_data, tenant_id, allow_superadmin=True)
    service = AccessControlPolicyService(db)
    snapshot = service.get_tenant_role_policy(tenant_id=tenant_id, role_name=role_name.upper())
    return RolePolicyResponse(
        tenant_id=tenant_id,
        role=role_name.upper(),
        allow=snapshot.allow,
        deny=snapshot.deny,
        trace_id=getattr(request.state, "trace_id", ""),
    )


@router.put("/tenants/{tenant_id}/role-policies/{role_name}", response_model=RolePolicyResponse)
async def replace_tenant_role_policy(
    request: Request,
    tenant_id: str,
    role_name: str,
    payload: RolePolicyRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    _require_admin(token_data)
    enforce_tenant_scope(token_data, tenant_id, allow_superadmin=True)
    idempotency_key = extract_idempotency_key(request.headers, required=True)
    request_hash = IdempotencyService.fingerprint(payload.model_dump(mode="json"))
    idempotency_service = IdempotencyService(db)
    context, replay = idempotency_service.start(
        tenant_id=tenant_id,
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

    service = AccessControlPolicyService(db)
    before, after = service.replace_tenant_role_policy(
        tenant_id=tenant_id,
        role_name=role_name.upper(),
        allow=payload.allow,
        deny=payload.deny,
        enforce_ceiling=not is_superadmin(token_data.role),
    )

    response = RolePolicyResponse(
        tenant_id=tenant_id,
        role=role_name.upper(),
        allow=after.allow,
        deny=after.deny,
        trace_id=getattr(request.state, "trace_id", ""),
    )
    context.record_success(status_code=200, response_body=response.model_dump())

    AuditService(db).record_event(
        AuditEventPayload(
            tenant_id=tenant_id,
            user_id=str(current_user.id),
            store_id=str(current_user.store_id) if current_user.store_id else None,
            trace_id=getattr(request.state, "trace_id", "") or None,
            actor=current_user.username,
            action="access_control.role_policy.update",
            entity_type="role_policy",
            entity_id=f"{tenant_id}:{role_name.upper()}",
            before={"allow": before.allow, "deny": before.deny},
            after={"allow": after.allow, "deny": after.deny},
            metadata={"role": role_name.upper()},
            result="success",
        )
    )
    return response


@router.get("/tenants/{tenant_id}/users/{user_id}/permission-overrides", response_model=UserPermissionOverrideResponse)
async def get_user_permission_overrides(
    request: Request,
    tenant_id: str,
    user_id: str,
    token_data=Depends(get_current_token_data),
    _current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    _require_admin(token_data)
    enforce_tenant_scope(token_data, tenant_id, allow_superadmin=True)
    user = UserRepository(db).get_by_id(user_id)
    if user is None or str(user.tenant_id) != tenant_id:
        raise AppError(ErrorCatalog.CROSS_TENANT_ACCESS_DENIED)
    service = AccessControlPolicyService(db)
    snapshot = service.get_user_overrides(tenant_id=tenant_id, user_id=user_id)
    return UserPermissionOverrideResponse(
        tenant_id=tenant_id,
        user_id=user_id,
        allow=snapshot.allow,
        deny=snapshot.deny,
        trace_id=getattr(request.state, "trace_id", ""),
    )


@router.put("/tenants/{tenant_id}/users/{user_id}/permission-overrides", response_model=UserPermissionOverrideResponse)
async def replace_user_permission_overrides(
    request: Request,
    tenant_id: str,
    user_id: str,
    payload: UserPermissionOverrideRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    _require_admin(token_data)
    enforce_tenant_scope(token_data, tenant_id, allow_superadmin=True)
    user = UserRepository(db).get_by_id(user_id)
    if user is None or str(user.tenant_id) != tenant_id:
        raise AppError(ErrorCatalog.CROSS_TENANT_ACCESS_DENIED)

    idempotency_key = extract_idempotency_key(request.headers, required=True)
    request_hash = IdempotencyService.fingerprint(payload.model_dump(mode="json"))
    idempotency_service = IdempotencyService(db)
    context, replay = idempotency_service.start(
        tenant_id=tenant_id,
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

    service = AccessControlPolicyService(db)
    before, after = service.replace_user_overrides(
        tenant_id=tenant_id,
        user_id=user_id,
        allow=payload.allow,
        deny=payload.deny,
        enforce_ceiling=not is_superadmin(token_data.role),
    )

    response = UserPermissionOverrideResponse(
        tenant_id=tenant_id,
        user_id=user_id,
        allow=after.allow,
        deny=after.deny,
        trace_id=getattr(request.state, "trace_id", ""),
    )
    context.record_success(status_code=200, response_body=response.model_dump())

    AuditService(db).record_event(
        AuditEventPayload(
            tenant_id=tenant_id,
            user_id=str(current_user.id),
            store_id=str(current_user.store_id) if current_user.store_id else None,
            trace_id=getattr(request.state, "trace_id", "") or None,
            actor=current_user.username,
            action="access_control.user_override.update",
            entity_type="user_override",
            entity_id=f"{tenant_id}:{user_id}",
            before={"allow": before.allow, "deny": before.deny},
            after={"allow": after.allow, "deny": after.deny},
            metadata={"user_id": user_id},
            result="success",
        )
    )
    return response


@router.get("/platform/role-policies/{role_name}", response_model=RolePolicyResponse)
async def get_platform_role_policy(
    request: Request,
    role_name: str,
    token_data=Depends(get_current_token_data),
    _current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    if not is_superadmin(token_data.role):
        raise AppError(ErrorCatalog.PERMISSION_DENIED)
    service = AccessControlPolicyService(db)
    snapshot = service.get_tenant_role_policy(tenant_id=None, role_name=role_name.upper())
    return RolePolicyResponse(
        tenant_id=None,
        role=role_name.upper(),
        allow=snapshot.allow,
        deny=snapshot.deny,
        trace_id=getattr(request.state, "trace_id", ""),
    )


@router.put("/platform/role-policies/{role_name}", response_model=RolePolicyResponse)
async def replace_platform_role_policy(
    request: Request,
    role_name: str,
    payload: RolePolicyRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    if not is_superadmin(token_data.role):
        raise AppError(ErrorCatalog.PERMISSION_DENIED)
    idempotency_key = extract_idempotency_key(request.headers, required=True)
    request_hash = IdempotencyService.fingerprint(payload.model_dump(mode="json"))
    idempotency_service = IdempotencyService(db)
    context, replay = idempotency_service.start(
        tenant_id=token_data.tenant_id,
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

    service = AccessControlPolicyService(db)
    before, after = service.replace_tenant_role_policy(
        tenant_id=None,
        role_name=role_name.upper(),
        allow=payload.allow,
        deny=payload.deny,
        enforce_ceiling=False,
    )

    response = RolePolicyResponse(
        tenant_id=None,
        role=role_name.upper(),
        allow=after.allow,
        deny=after.deny,
        trace_id=getattr(request.state, "trace_id", ""),
    )
    context.record_success(status_code=200, response_body=response.model_dump())

    AuditService(db).record_event(
        AuditEventPayload(
            tenant_id=token_data.tenant_id or "",
            user_id=str(current_user.id),
            store_id=str(current_user.store_id) if current_user.store_id else None,
            trace_id=getattr(request.state, "trace_id", "") or None,
            actor=current_user.username,
            action="access_control.platform_role_policy.update",
            entity_type="role_policy",
            entity_id=f"platform:{role_name.upper()}",
            before={"allow": before.allow, "deny": before.deny},
            after={"allow": after.allow, "deny": after.deny},
            metadata={"role": role_name.upper()},
            result="success",
        )
    )
    return response


def _require_admin(token_data) -> None:
    role = (token_data.role or "").upper()
    if role == "ADMIN":
        return
    if is_superadmin(role):
        return
    raise AppError(ErrorCatalog.PERMISSION_DENIED)
