from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.aris3.core.context import build_request_context
from app.aris3.core.deps import get_current_token_data, require_active_user, require_request_context
from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.core.scope import enforce_store_scope, enforce_tenant_scope, is_superadmin
from app.aris3.db.session import get_db
from app.aris3.repos.users import UserRepository
from app.aris3.schemas.access_control import (
    EffectivePermissionsResponse,
    EffectivePermissionSubject,
    EffectivePermissionsTrace,
    PermissionCatalogEntry,
    PermissionCatalogResponse,
    PermissionEntry,
    PermissionSourceTrace,
    RolePolicyRequest,
    RolePolicyResponse,
    StoreRolePolicyResponse,
    UserPermissionOverrideRequest,
    UserPermissionOverrideResponse,
)
from app.aris3.services.access_control import AccessControlService
from app.aris3.services.access_control_policies import AccessControlPolicyService
from app.aris3.services.audit import AuditEventPayload, AuditService
from app.aris3.services.idempotency import IdempotencyService, extract_idempotency_key

router = APIRouter()


@router.get("/effective-permissions", response_model=EffectivePermissionsResponse, description="Effective Permissions = resultado final tras Role Template + Tenant/Store policies + User Overrides.")
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
    decisions, trace = service.build_effective_permissions_with_trace(context, token_data)
    denies_applied = sorted(
        {entry.key for entry in decisions if entry.source in {"explicit_deny", "user_override_deny", "store_policy_deny", "tenant_policy_deny"}}
    )
    return EffectivePermissionsResponse(
        user_id=context.user_id or token_data.sub,
        tenant_id=context.tenant_id or token_data.tenant_id,
        store_id=context.store_id or token_data.store_id,
        role=(context.role or token_data.role),
        permissions=[PermissionEntry(key=d.key, allowed=d.allowed, source=d.source) for d in decisions],
        subject=EffectivePermissionSubject(
            user_id=context.user_id or token_data.sub,
            tenant_id=context.tenant_id or token_data.tenant_id,
            store_id=context.store_id or token_data.store_id,
            role=(context.role or token_data.role),
        ),
        denies_applied=denies_applied,
        sources_trace=EffectivePermissionsTrace(
            template=PermissionSourceTrace(allow=sorted(trace.template_allow), deny=[]),
            tenant=PermissionSourceTrace(
                allow=sorted(trace.tenant_allow),
                deny=sorted(trace.tenant_deny),
            ),
            store=PermissionSourceTrace(
                allow=sorted(trace.store_allow),
                deny=sorted(trace.store_deny),
            ),
            user=PermissionSourceTrace(
                allow=sorted(trace.user_allow),
                deny=sorted(trace.user_deny),
            ),
        ),
        trace_id=getattr(request.state, "trace_id", ""),
    )


@router.get("/effective-permissions/users/{user_id}", response_model=EffectivePermissionsResponse, description="Computes effective permissions for a target user using full policy layering.")
async def effective_permissions_for_user(
    request: Request,
    user_id: str,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    role = (token_data.role or "").upper()
    if not is_superadmin(role) and role != "ADMIN":
        if user_id != token_data.sub:
            raise AppError(ErrorCatalog.PERMISSION_DENIED)

    target_user = current_user if user_id == str(current_user.id) else UserRepository(db).get_by_id(user_id)
    if target_user is None:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "User not found"})

    if not is_superadmin(role):
        if not token_data.tenant_id or str(target_user.tenant_id) != token_data.tenant_id:
            raise AppError(ErrorCatalog.CROSS_TENANT_ACCESS_DENIED)
        _enforce_user_store_scope(token_data, target_user)

    cache = getattr(request.state, "permission_cache", None)
    if cache is None:
        cache = {}
        request.state.permission_cache = cache
    service = AccessControlService(db, cache=cache)
    context = build_request_context(
        user_id=str(target_user.id),
        tenant_id=str(target_user.tenant_id),
        store_id=str(target_user.store_id) if target_user.store_id else None,
        role=target_user.role,
        trace_id=getattr(request.state, "trace_id", ""),
    )
    decisions, trace = service.build_effective_permissions_with_trace(context, None)
    denies_applied = sorted(
        {entry.key for entry in decisions if entry.source in {"explicit_deny", "user_override_deny", "store_policy_deny", "tenant_policy_deny"}}
    )
    return EffectivePermissionsResponse(
        user_id=str(target_user.id),
        tenant_id=str(target_user.tenant_id),
        store_id=str(target_user.store_id) if target_user.store_id else None,
        role=target_user.role,
        permissions=[PermissionEntry(key=d.key, allowed=d.allowed, source=d.source) for d in decisions],
        subject=EffectivePermissionSubject(
            user_id=str(target_user.id),
            tenant_id=str(target_user.tenant_id),
            store_id=str(target_user.store_id) if target_user.store_id else None,
            role=target_user.role,
        ),
        denies_applied=denies_applied,
        sources_trace=EffectivePermissionsTrace(
            template=PermissionSourceTrace(allow=sorted(trace.template_allow), deny=[]),
            tenant=PermissionSourceTrace(
                allow=sorted(trace.tenant_allow),
                deny=sorted(trace.tenant_deny),
            ),
            store=PermissionSourceTrace(
                allow=sorted(trace.store_allow),
                deny=sorted(trace.store_deny),
            ),
            user=PermissionSourceTrace(
                allow=sorted(trace.user_allow),
                deny=sorted(trace.user_deny),
            ),
        ),
        trace_id=getattr(request.state, "trace_id", ""),
    )


@router.get(
    "/tenants/{tenant_id}/stores/{store_id}/users/{user_id}/effective-permissions",
    response_model=EffectivePermissionsResponse,
)
async def effective_permissions_for_store_user(
    request: Request,
    tenant_id: str,
    store_id: str,
    user_id: str,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    _require_admin(token_data)
    enforce_tenant_scope(token_data, tenant_id, allow_superadmin=True)
    store = enforce_store_scope(
        token_data,
        store_id,
        db,
        allow_superadmin=True,
        broader_store_roles={"SUPERADMIN"},
    )
    if str(store.tenant_id) != tenant_id:
        raise AppError(ErrorCatalog.STORE_SCOPE_MISMATCH)

    target_user = current_user if user_id == str(current_user.id) else UserRepository(db).get_by_id(user_id)
    if target_user is None:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "User not found"})
    if str(target_user.tenant_id) != tenant_id or str(target_user.store_id) != store_id:
        raise AppError(ErrorCatalog.STORE_SCOPE_MISMATCH)

    cache = getattr(request.state, "permission_cache", None)
    if cache is None:
        cache = {}
        request.state.permission_cache = cache
    service = AccessControlService(db, cache=cache)
    context = build_request_context(
        user_id=str(target_user.id),
        tenant_id=str(target_user.tenant_id),
        store_id=str(target_user.store_id) if target_user.store_id else None,
        role=target_user.role,
        trace_id=getattr(request.state, "trace_id", ""),
    )
    decisions, trace = service.build_effective_permissions_with_trace(context, None)
    denies_applied = sorted(
        {entry.key for entry in decisions if entry.source in {"explicit_deny", "user_override_deny", "store_policy_deny", "tenant_policy_deny"}}
    )
    return EffectivePermissionsResponse(
        user_id=str(target_user.id),
        tenant_id=str(target_user.tenant_id),
        store_id=str(target_user.store_id) if target_user.store_id else None,
        role=target_user.role,
        permissions=[PermissionEntry(key=d.key, allowed=d.allowed, source=d.source) for d in decisions],
        subject=EffectivePermissionSubject(
            user_id=str(target_user.id),
            tenant_id=str(target_user.tenant_id),
            store_id=str(target_user.store_id) if target_user.store_id else None,
            role=target_user.role,
        ),
        denies_applied=denies_applied,
        sources_trace=EffectivePermissionsTrace(
            template=PermissionSourceTrace(allow=sorted(trace.template_allow), deny=[]),
            tenant=PermissionSourceTrace(
                allow=sorted(trace.tenant_allow),
                deny=sorted(trace.tenant_deny),
            ),
            store=PermissionSourceTrace(
                allow=sorted(trace.store_allow),
                deny=sorted(trace.store_deny),
            ),
            user=PermissionSourceTrace(
                allow=sorted(trace.user_allow),
                deny=sorted(trace.user_deny),
            ),
        ),
        trace_id=getattr(request.state, "trace_id", ""),
    )


@router.get("/permission-catalog", response_model=PermissionCatalogResponse, description="Permission catalog available for role templates, policies, and overrides.")
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
    _require_transaction_id(payload.transaction_id)
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


@router.get(
    "/tenants/{tenant_id}/stores/{store_id}/role-policies/{role_name}",
    response_model=StoreRolePolicyResponse,
)
async def get_store_role_policy(
    request: Request,
    tenant_id: str,
    store_id: str,
    role_name: str,
    token_data=Depends(get_current_token_data),
    _current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    _require_admin(token_data)
    enforce_tenant_scope(token_data, tenant_id, allow_superadmin=True)
    store = enforce_store_scope(
        token_data,
        store_id,
        db,
        allow_superadmin=True,
        broader_store_roles={"SUPERADMIN"},
    )
    if str(store.tenant_id) != tenant_id:
        raise AppError(ErrorCatalog.STORE_SCOPE_MISMATCH)
    service = AccessControlPolicyService(db)
    snapshot = service.get_store_role_policy(
        tenant_id=tenant_id,
        store_id=store_id,
        role_name=role_name.upper(),
    )
    return StoreRolePolicyResponse(
        tenant_id=tenant_id,
        store_id=store_id,
        role=role_name.upper(),
        allow=snapshot.allow,
        deny=snapshot.deny,
        trace_id=getattr(request.state, "trace_id", ""),
    )


@router.put(
    "/tenants/{tenant_id}/stores/{store_id}/role-policies/{role_name}",
    response_model=StoreRolePolicyResponse,
)
async def replace_store_role_policy(
    request: Request,
    tenant_id: str,
    store_id: str,
    role_name: str,
    payload: RolePolicyRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    _require_admin(token_data)
    enforce_tenant_scope(token_data, tenant_id, allow_superadmin=True)
    store = enforce_store_scope(
        token_data,
        store_id,
        db,
        allow_superadmin=True,
        broader_store_roles={"SUPERADMIN"},
    )
    if str(store.tenant_id) != tenant_id:
        raise AppError(ErrorCatalog.STORE_SCOPE_MISMATCH)
    _require_transaction_id(payload.transaction_id)
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
    before, after = service.replace_store_role_policy(
        tenant_id=tenant_id,
        store_id=store_id,
        role_name=role_name.upper(),
        allow=payload.allow,
        deny=payload.deny,
        enforce_ceiling=not is_superadmin(token_data.role),
    )

    response = StoreRolePolicyResponse(
        tenant_id=tenant_id,
        store_id=store_id,
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
            action="access_control.store_role_policy.update",
            entity_type="role_policy",
            entity_id=f"{tenant_id}:{store_id}:{role_name.upper()}",
            before={"allow": before.allow, "deny": before.deny},
            after={"allow": after.allow, "deny": after.deny},
            metadata={"role": role_name.upper(), "store_id": store_id},
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
    _enforce_user_store_scope(token_data, user)
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
    _enforce_user_store_scope(token_data, user)

    _require_transaction_id(payload.transaction_id)
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
    _require_transaction_id(payload.transaction_id)
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


def _require_transaction_id(transaction_id: str | None) -> None:
    if not transaction_id:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "transaction_id is required"},
        )


def _enforce_user_store_scope(token_data, user) -> None:
    if is_superadmin(token_data.role):
        return
    if token_data.store_id:
        user_store_id = str(user.store_id) if user.store_id else None
        if user_store_id != token_data.store_id:
            raise AppError(ErrorCatalog.STORE_SCOPE_MISMATCH)
