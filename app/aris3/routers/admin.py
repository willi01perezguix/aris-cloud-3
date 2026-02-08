import secrets
import string
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.aris3.core.deps import (
    get_current_token_data,
    require_active_user,
    require_permission,
    require_request_context,
)
from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.core.scope import is_superadmin
from app.aris3.core.security import get_password_hash
from app.aris3.db.models import Store, Tenant, User, VariantFieldSettings
from app.aris3.db.session import get_db
from app.aris3.repos.rbac import RoleTemplateRepository
from app.aris3.repos.settings import VariantFieldSettingsRepository
from app.aris3.repos.stores import StoreRepository
from app.aris3.repos.tenants import TenantRepository
from app.aris3.repos.users import UserRepository
from app.aris3.schemas.admin import (
    StoreCreateRequest,
    StoreListResponse,
    StoreResponse,
    StoreUpdateRequest,
    TenantActionRequest,
    TenantActionResponse,
    TenantCreateRequest,
    TenantListResponse,
    TenantResponse,
    TenantUpdateRequest,
    UserActionRequest,
    UserActionResponse,
    UserCreateRequest,
    UserListResponse,
    UserResponse,
    UserUpdateRequest,
    VariantFieldSettingsPatchRequest,
    VariantFieldSettingsResponse,
)
from app.aris3.services.access_control import AccessControlService
from app.aris3.services.audit import AuditEventPayload, AuditService
from app.aris3.services.idempotency import IdempotencyService, extract_idempotency_key


router = APIRouter()


def _tenant_id_or_error(token_data) -> str:
    if not token_data.tenant_id:
        raise AppError(ErrorCatalog.TENANT_SCOPE_REQUIRED)
    return token_data.tenant_id


def _store_item(store: Store) -> dict:
    return {
        "id": str(store.id),
        "tenant_id": str(store.tenant_id),
        "name": store.name,
        "created_at": store.created_at,
    }


def _tenant_item(tenant: Tenant) -> dict:
    return {
        "id": str(tenant.id),
        "name": tenant.name,
        "status": tenant.status,
        "created_at": tenant.created_at,
    }


def _user_item(user: User) -> dict:
    return {
        "id": str(user.id),
        "tenant_id": str(user.tenant_id),
        "store_id": str(user.store_id) if user.store_id else None,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "status": user.status,
        "is_active": user.is_active,
        "must_change_password": user.must_change_password,
        "created_at": user.created_at,
    }


def _validate_password(password: str) -> None:
    if len(password) < 8:
        raise AppError(ErrorCatalog.PASSWORD_TOO_SHORT)
    has_letter = any(char.isalpha() for char in password)
    has_digit = any(char.isdigit() for char in password)
    if not (has_letter and has_digit):
        raise AppError(ErrorCatalog.PASSWORD_COMPLEXITY)


def _generate_temporary_password() -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(12))
        try:
            _validate_password(password)
        except AppError:
            continue
        return password


def _normalize_role(role: str) -> str:
    return role.strip().upper()


def _require_superadmin(token_data) -> None:
    if not is_superadmin(token_data.role):
        raise AppError(ErrorCatalog.PERMISSION_DENIED)


def _ensure_role_assignment_allowed(
    request: Request,
    *,
    desired_role: str,
    token_data,
    context,
    db,
) -> str:
    normalized = _normalize_role(desired_role)
    if is_superadmin(normalized):
        raise AppError(ErrorCatalog.PERMISSION_DENIED)
    if normalized == "ADMIN" and not is_superadmin(token_data.role):
        tenant_id = context.tenant_id or token_data.tenant_id
        role_repo = RoleTemplateRepository(db)
        admin_permissions = set(role_repo.list_permissions_for_role("ADMIN", tenant_id))
        if not admin_permissions and tenant_id is not None:
            admin_permissions = set(role_repo.list_permissions_for_role("ADMIN", None))
        cache = getattr(request.state, "permission_cache", None)
        if cache is None:
            cache = {}
            request.state.permission_cache = cache
        service = AccessControlService(db, cache=cache)
        allowed = {d.key for d in service.build_effective_permissions(context, token_data) if d.allowed}
        if admin_permissions and not admin_permissions.issubset(allowed):
            raise AppError(
                ErrorCatalog.PERMISSION_DENIED,
                details={
                    "message": "ADMIN ceiling exceeded",
                    "missing": sorted(admin_permissions.difference(allowed)),
                },
            )
    return normalized


@router.get("/tenants", response_model=TenantListResponse)
async def list_tenants(
    request: Request,
    token_data=Depends(get_current_token_data),
    _current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    _require_superadmin(token_data)
    tenants = TenantRepository(db).list_all()
    return TenantListResponse(
        tenants=[_tenant_item(tenant) for tenant in tenants],
        trace_id=getattr(request.state, "trace_id", ""),
    )


@router.post("/tenants", response_model=TenantResponse, status_code=201)
async def create_tenant(
    request: Request,
    payload: TenantCreateRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    _require_superadmin(token_data)
    idempotency_key = extract_idempotency_key(request.headers, required=True)
    request_hash = IdempotencyService.fingerprint(payload.model_dump(mode="json"))
    idempotency_service = IdempotencyService(db)
    context, replay = idempotency_service.start(
        tenant_id=token_data.tenant_id or "platform",
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

    repo = TenantRepository(db)
    existing = repo.get_by_name(payload.name)
    if existing:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "Tenant name already exists", "name": payload.name},
        )

    tenant = repo.create(Tenant(name=payload.name, status="active"))
    response = TenantResponse(
        tenant=_tenant_item(tenant),
        trace_id=getattr(request.state, "trace_id", ""),
    )
    context.record_success(status_code=201, response_body=response.model_dump(mode="json"))

    AuditService(db).record_event(
        AuditEventPayload(
            tenant_id=str(tenant.id),
            user_id=str(current_user.id),
            store_id=str(current_user.store_id) if current_user.store_id else None,
            trace_id=getattr(request.state, "trace_id", "") or None,
            actor=current_user.username,
            action="admin.tenant.create",
            entity_type="tenant",
            entity_id=str(tenant.id),
            before=None,
            after={"name": tenant.name, "status": tenant.status},
            metadata=None,
            result="success",
        )
    )
    return response


@router.get("/tenants/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    request: Request,
    tenant_id: str,
    token_data=Depends(get_current_token_data),
    _current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    _require_superadmin(token_data)
    tenant = TenantRepository(db).get_by_id(tenant_id)
    if tenant is None:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "Tenant not found"})
    return TenantResponse(
        tenant=_tenant_item(tenant),
        trace_id=getattr(request.state, "trace_id", ""),
    )


@router.patch("/tenants/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    request: Request,
    tenant_id: str,
    payload: TenantUpdateRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    _require_superadmin(token_data)
    tenant = TenantRepository(db).get_by_id(tenant_id)
    if tenant is None:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "Tenant not found"})

    idempotency_key = extract_idempotency_key(request.headers, required=True)
    request_hash = IdempotencyService.fingerprint(payload.model_dump(mode="json"))
    idempotency_service = IdempotencyService(db)
    context, replay = idempotency_service.start(
        tenant_id=str(tenant.id),
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

    repo = TenantRepository(db)
    existing = repo.get_by_name(payload.name)
    if existing and str(existing.id) != tenant_id:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "Tenant name already exists", "name": payload.name},
        )

    before = {"name": tenant.name, "status": tenant.status}
    tenant.name = payload.name
    repo.update(tenant)

    response = TenantResponse(
        tenant=_tenant_item(tenant),
        trace_id=getattr(request.state, "trace_id", ""),
    )
    context.record_success(status_code=200, response_body=response.model_dump(mode="json"))

    AuditService(db).record_event(
        AuditEventPayload(
            tenant_id=str(tenant.id),
            user_id=str(current_user.id),
            store_id=str(current_user.store_id) if current_user.store_id else None,
            trace_id=getattr(request.state, "trace_id", "") or None,
            actor=current_user.username,
            action="admin.tenant.update",
            entity_type="tenant",
            entity_id=str(tenant.id),
            before=before,
            after={"name": tenant.name, "status": tenant.status},
            metadata=None,
            result="success",
        )
    )
    return response


@router.post("/tenants/{tenant_id}/actions", response_model=TenantActionResponse)
async def tenant_actions(
    request: Request,
    tenant_id: str,
    payload: TenantActionRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    _require_superadmin(token_data)
    tenant = TenantRepository(db).get_by_id(tenant_id)
    if tenant is None:
        raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "Tenant not found"})

    idempotency_key = extract_idempotency_key(request.headers, required=True)
    request_hash = IdempotencyService.fingerprint(payload.model_dump(mode="json"))
    idempotency_service = IdempotencyService(db)
    context, replay = idempotency_service.start(
        tenant_id=str(tenant.id),
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

    before = {"name": tenant.name, "status": tenant.status}
    if payload.action == "set_status":
        if payload.status is None:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "status is required for set_status"},
            )
        normalized = payload.status.upper()
        if normalized == "ACTIVE":
            tenant.status = "active"
        elif normalized == "SUSPENDED":
            tenant.status = "suspended"
        else:
            tenant.status = "canceled"
    else:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "Unsupported action", "action": payload.action},
        )

    TenantRepository(db).update(tenant)

    response = TenantActionResponse(
        tenant=_tenant_item(tenant),
        action=payload.action,
        trace_id=getattr(request.state, "trace_id", ""),
    )
    context.record_success(status_code=200, response_body=response.model_dump(mode="json"))

    AuditService(db).record_event(
        AuditEventPayload(
            tenant_id=str(tenant.id),
            user_id=str(current_user.id),
            store_id=str(current_user.store_id) if current_user.store_id else None,
            trace_id=getattr(request.state, "trace_id", "") or None,
            actor=current_user.username,
            action="admin.tenant.set_status",
            entity_type="tenant",
            entity_id=str(tenant.id),
            before=before,
            after={"name": tenant.name, "status": tenant.status},
            metadata={"action": payload.action},
            result="success",
        )
    )
    return response


@router.get("/stores", response_model=StoreListResponse)
async def list_stores(
    request: Request,
    token_data=Depends(get_current_token_data),
    _current_user=Depends(require_active_user),
    _permission=Depends(require_permission("STORE_VIEW")),
    db=Depends(get_db),
):
    tenant_id = _tenant_id_or_error(token_data)
    stores = StoreRepository(db).list_by_tenant(tenant_id)
    return StoreListResponse(
        stores=[_store_item(store) for store in stores],
        trace_id=getattr(request.state, "trace_id", ""),
    )


@router.post("/stores", response_model=StoreResponse, status_code=201)
async def create_store(
    request: Request,
    payload: StoreCreateRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    _permission=Depends(require_permission("STORE_MANAGE")),
    db=Depends(get_db),
):
    tenant_id = _tenant_id_or_error(token_data)
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

    repo = StoreRepository(db)
    store = repo.create(Store(tenant_id=tenant_id, name=payload.name))

    response = StoreResponse(
        store=_store_item(store),
        trace_id=getattr(request.state, "trace_id", ""),
    )
    context.record_success(status_code=201, response_body=response.model_dump(mode="json"))

    AuditService(db).record_event(
        AuditEventPayload(
            tenant_id=tenant_id,
            user_id=str(current_user.id),
            store_id=str(current_user.store_id) if current_user.store_id else None,
            trace_id=getattr(request.state, "trace_id", "") or None,
            actor=current_user.username,
            action="admin.store.create",
            entity_type="store",
            entity_id=str(store.id),
            before=None,
            after={"name": store.name},
            metadata=None,
            result="success",
        )
    )
    return response


@router.get("/stores/{store_id}", response_model=StoreResponse)
async def get_store(
    request: Request,
    store_id: str,
    token_data=Depends(get_current_token_data),
    _current_user=Depends(require_active_user),
    _permission=Depends(require_permission("STORE_VIEW")),
    db=Depends(get_db),
):
    tenant_id = _tenant_id_or_error(token_data)
    store = StoreRepository(db).get_by_id(store_id)
    if store is None or str(store.tenant_id) != tenant_id:
        raise AppError(ErrorCatalog.CROSS_TENANT_ACCESS_DENIED)
    return StoreResponse(
        store=_store_item(store),
        trace_id=getattr(request.state, "trace_id", ""),
    )


@router.patch("/stores/{store_id}", response_model=StoreResponse)
async def update_store(
    request: Request,
    store_id: str,
    payload: StoreUpdateRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    _permission=Depends(require_permission("STORE_MANAGE")),
    db=Depends(get_db),
):
    tenant_id = _tenant_id_or_error(token_data)
    store = StoreRepository(db).get_by_id(store_id)
    if store is None or str(store.tenant_id) != tenant_id:
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

    before = {"name": store.name}
    store.name = payload.name
    StoreRepository(db).update(store)

    response = StoreResponse(
        store=_store_item(store),
        trace_id=getattr(request.state, "trace_id", ""),
    )
    context.record_success(status_code=200, response_body=response.model_dump(mode="json"))

    AuditService(db).record_event(
        AuditEventPayload(
            tenant_id=tenant_id,
            user_id=str(current_user.id),
            store_id=str(current_user.store_id) if current_user.store_id else None,
            trace_id=getattr(request.state, "trace_id", "") or None,
            actor=current_user.username,
            action="admin.store.update",
            entity_type="store",
            entity_id=str(store.id),
            before=before,
            after={"name": store.name},
            metadata=None,
            result="success",
        )
    )
    return response


@router.get("/users", response_model=UserListResponse)
async def list_users(
    request: Request,
    token_data=Depends(get_current_token_data),
    _current_user=Depends(require_active_user),
    _permission=Depends(require_permission("USER_MANAGE")),
    db=Depends(get_db),
):
    tenant_id = _tenant_id_or_error(token_data)
    users = db.query(User).filter(User.tenant_id == tenant_id).order_by(User.username).all()
    return UserListResponse(
        users=[_user_item(user) for user in users],
        trace_id=getattr(request.state, "trace_id", ""),
    )


@router.post("/users", response_model=UserResponse, status_code=201)
async def create_user(
    request: Request,
    payload: UserCreateRequest,
    token_data=Depends(get_current_token_data),
    context=Depends(require_request_context),
    current_user=Depends(require_active_user),
    _permission=Depends(require_permission("USER_MANAGE")),
    db=Depends(get_db),
):
    tenant_id = _tenant_id_or_error(token_data)
    idempotency_key = extract_idempotency_key(request.headers, required=True)
    request_hash = IdempotencyService.fingerprint(payload.model_dump(mode="json"))
    idempotency_service = IdempotencyService(db)
    context_idempotency, replay = idempotency_service.start(
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
    request.state.idempotency = context_idempotency

    _validate_password(payload.password)
    normalized_role = _ensure_role_assignment_allowed(
        request,
        desired_role=payload.role,
        token_data=token_data,
        context=context,
        db=db,
    )

    store_id = payload.store_id
    if store_id:
        store = StoreRepository(db).get_by_id(store_id)
        if store is None or str(store.tenant_id) != tenant_id:
            raise AppError(ErrorCatalog.CROSS_TENANT_ACCESS_DENIED)

    user = User(
        tenant_id=tenant_id,
        store_id=store_id,
        username=payload.username,
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        role=normalized_role,
        status="active",
        must_change_password=True,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    response = UserResponse(
        user=_user_item(user),
        trace_id=getattr(request.state, "trace_id", ""),
    )
    context_idempotency.record_success(status_code=201, response_body=response.model_dump(mode="json"))

    AuditService(db).record_event(
        AuditEventPayload(
            tenant_id=tenant_id,
            user_id=str(current_user.id),
            store_id=str(current_user.store_id) if current_user.store_id else None,
            trace_id=getattr(request.state, "trace_id", "") or None,
            actor=current_user.username,
            action="admin.user.create",
            entity_type="user",
            entity_id=str(user.id),
            before=None,
            after={"username": user.username, "email": user.email, "role": user.role},
            metadata=None,
            result="success",
        )
    )
    return response


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    request: Request,
    user_id: str,
    token_data=Depends(get_current_token_data),
    _current_user=Depends(require_active_user),
    _permission=Depends(require_permission("USER_MANAGE")),
    db=Depends(get_db),
):
    tenant_id = _tenant_id_or_error(token_data)
    user = UserRepository(db).get_by_id(user_id)
    if user is None or str(user.tenant_id) != tenant_id:
        raise AppError(ErrorCatalog.CROSS_TENANT_ACCESS_DENIED)
    return UserResponse(
        user=_user_item(user),
        trace_id=getattr(request.state, "trace_id", ""),
    )


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    request: Request,
    user_id: str,
    payload: UserUpdateRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    _permission=Depends(require_permission("USER_MANAGE")),
    db=Depends(get_db),
):
    tenant_id = _tenant_id_or_error(token_data)
    user = UserRepository(db).get_by_id(user_id)
    if user is None or str(user.tenant_id) != tenant_id:
        raise AppError(ErrorCatalog.CROSS_TENANT_ACCESS_DENIED)

    if payload.username is None and payload.email is None and payload.store_id is None:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "At least one field must be provided"},
        )

    if payload.store_id:
        store = StoreRepository(db).get_by_id(payload.store_id)
        if store is None or str(store.tenant_id) != tenant_id:
            raise AppError(ErrorCatalog.CROSS_TENANT_ACCESS_DENIED)

    idempotency_key = extract_idempotency_key(request.headers, required=True)
    request_hash = IdempotencyService.fingerprint(payload.model_dump(mode="json"))
    idempotency_service = IdempotencyService(db)
    context_idempotency, replay = idempotency_service.start(
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
    request.state.idempotency = context_idempotency

    before = {"username": user.username, "email": user.email, "store_id": str(user.store_id)}
    if payload.username is not None:
        user.username = payload.username
    if payload.email is not None:
        user.email = payload.email
    if payload.store_id is not None:
        user.store_id = payload.store_id

    db.add(user)
    db.commit()
    db.refresh(user)

    response = UserResponse(
        user=_user_item(user),
        trace_id=getattr(request.state, "trace_id", ""),
    )
    context_idempotency.record_success(status_code=200, response_body=response.model_dump(mode="json"))

    AuditService(db).record_event(
        AuditEventPayload(
            tenant_id=tenant_id,
            user_id=str(current_user.id),
            store_id=str(current_user.store_id) if current_user.store_id else None,
            trace_id=getattr(request.state, "trace_id", "") or None,
            actor=current_user.username,
            action="admin.user.update",
            entity_type="user",
            entity_id=str(user.id),
            before=before,
            after={"username": user.username, "email": user.email, "store_id": str(user.store_id)},
            metadata=None,
            result="success",
        )
    )
    return response


@router.post("/users/{user_id}/actions", response_model=UserActionResponse)
async def user_actions(
    request: Request,
    user_id: str,
    payload: UserActionRequest,
    token_data=Depends(get_current_token_data),
    context=Depends(require_request_context),
    current_user=Depends(require_active_user),
    _permission=Depends(require_permission("USER_MANAGE")),
    db=Depends(get_db),
):
    tenant_id = _tenant_id_or_error(token_data)
    user = UserRepository(db).get_by_id(user_id)
    if user is None or str(user.tenant_id) != tenant_id:
        raise AppError(ErrorCatalog.CROSS_TENANT_ACCESS_DENIED)

    idempotency_key = extract_idempotency_key(request.headers, required=True)
    request_hash = IdempotencyService.fingerprint(payload.model_dump(mode="json"))
    idempotency_service = IdempotencyService(db)
    context_idempotency, replay = idempotency_service.start(
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
    request.state.idempotency = context_idempotency

    before = {
        "status": user.status,
        "role": user.role,
        "must_change_password": user.must_change_password,
    }
    temporary_password = None
    action = payload.action
    if action == "set_status":
        if payload.status is None:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "status is required for set_status"},
            )
        normalized = payload.status.upper()
        if normalized == "ACTIVE":
            user.status = "active"
            user.is_active = True
        elif normalized == "SUSPENDED":
            user.status = "suspended"
            user.is_active = False
        else:
            user.status = "canceled"
            user.is_active = False
    elif action == "set_role":
        if payload.role is None:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={"message": "role is required for set_role"},
            )
        normalized_role = _ensure_role_assignment_allowed(
            request,
            desired_role=payload.role,
            token_data=token_data,
            context=context,
            db=db,
        )
        user.role = normalized_role
    elif action == "reset_password":
        temporary_password = payload.temporary_password or _generate_temporary_password()
        _validate_password(temporary_password)
        user.hashed_password = get_password_hash(temporary_password)
        user.must_change_password = True
    else:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "Unsupported action", "action": action},
        )

    db.add(user)
    db.commit()
    db.refresh(user)

    response = UserActionResponse(
        user=_user_item(user),
        action=action,
        temporary_password=temporary_password,
        trace_id=getattr(request.state, "trace_id", ""),
    )
    context_idempotency.record_success(status_code=200, response_body=response.model_dump(mode="json"))

    AuditService(db).record_event(
        AuditEventPayload(
            tenant_id=tenant_id,
            user_id=str(current_user.id),
            store_id=str(current_user.store_id) if current_user.store_id else None,
            trace_id=getattr(request.state, "trace_id", "") or None,
            actor=current_user.username,
            action=f"admin.user.{action}",
            entity_type="user",
            entity_id=str(user.id),
            before=before,
            after={
                "status": user.status,
                "role": user.role,
                "must_change_password": user.must_change_password,
            },
            metadata={"temporary_password_set": temporary_password is not None},
            result="success",
        )
    )
    return response


@router.get("/settings/variant-fields", response_model=VariantFieldSettingsResponse)
async def get_variant_fields(
    request: Request,
    token_data=Depends(get_current_token_data),
    _current_user=Depends(require_active_user),
    _permission=Depends(require_permission("TENANT_VIEW")),
    db=Depends(get_db),
):
    tenant_id = _tenant_id_or_error(token_data)
    settings = VariantFieldSettingsRepository(db).get_by_tenant_id(tenant_id)
    return VariantFieldSettingsResponse(
        var1_label=settings.var1_label if settings else None,
        var2_label=settings.var2_label if settings else None,
        trace_id=getattr(request.state, "trace_id", ""),
    )


@router.patch("/settings/variant-fields", response_model=VariantFieldSettingsResponse)
async def patch_variant_fields(
    request: Request,
    payload: VariantFieldSettingsPatchRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    _permission=Depends(require_permission("SETTINGS_MANAGE")),
    db=Depends(get_db),
):
    tenant_id = _tenant_id_or_error(token_data)
    if payload.var1_label is None and payload.var2_label is None:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "At least one field must be provided"},
        )

    idempotency_key = extract_idempotency_key(request.headers, required=True)
    request_hash = IdempotencyService.fingerprint(payload.model_dump(mode="json"))
    idempotency_service = IdempotencyService(db)
    context_idempotency, replay = idempotency_service.start(
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
    request.state.idempotency = context_idempotency

    repo = VariantFieldSettingsRepository(db)
    settings = repo.get_by_tenant_id(tenant_id)
    before = None
    if settings is None:
        settings = VariantFieldSettings(
            tenant_id=tenant_id,
            var1_label=payload.var1_label,
            var2_label=payload.var2_label,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        repo.create(settings)
    else:
        before = {"var1_label": settings.var1_label, "var2_label": settings.var2_label}
        if payload.var1_label is not None:
            settings.var1_label = payload.var1_label
        if payload.var2_label is not None:
            settings.var2_label = payload.var2_label
        settings.updated_at = datetime.utcnow()
        repo.update(settings)

    response = VariantFieldSettingsResponse(
        var1_label=settings.var1_label,
        var2_label=settings.var2_label,
        trace_id=getattr(request.state, "trace_id", ""),
    )
    context_idempotency.record_success(status_code=200, response_body=response.model_dump())

    AuditService(db).record_event(
        AuditEventPayload(
            tenant_id=tenant_id,
            user_id=str(current_user.id),
            store_id=str(current_user.store_id) if current_user.store_id else None,
            trace_id=getattr(request.state, "trace_id", "") or None,
            actor=current_user.username,
            action="admin.settings.variant_fields.update",
            entity_type="variant_field_settings",
            entity_id=str(settings.id),
            before=before,
            after={"var1_label": settings.var1_label, "var2_label": settings.var2_label},
            metadata=None,
            result="success",
        )
    )
    return response
