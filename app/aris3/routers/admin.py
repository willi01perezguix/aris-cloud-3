import logging
import secrets
import string
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select

from app.aris3.core.context import build_request_context
from app.aris3.core.deps import (
    get_current_token_data,
    require_active_user,
    require_permission,
    require_request_context,
)
from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.core.scope import enforce_store_scope, is_superadmin
from app.aris3.core.security import get_password_hash
from app.aris3.db.models import (
    ExportRecord,
    PosCashDayClose,
    PosCashMovement,
    PosCashSession,
    PosPayment,
    PosReturnEvent,
    PosSale,
    PosSaleLine,
    ReturnPolicySettings,
    StockItem,
    Store,
    StoreRolePolicy,
    Tenant,
    TenantRolePolicy,
    Transfer,
    TransferLine,
    TransferMovement,
    User,
    UserPermissionOverride,
    VariantFieldSettings,
)
from app.aris3.db.session import get_db
from app.aris3.repos.rbac import RoleTemplateRepository
from app.aris3.repos.settings import ReturnPolicySettingsRepository, VariantFieldSettingsRepository
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
    ReturnPolicySettingsPatchRequest,
    ReturnPolicySettingsResponse,
    AdminDeleteConflictResponse,
    AdminDeleteResponse,
    VariantFieldSettingsPatchRequest,
    VariantFieldSettingsResponse,
)
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
    RoleTemplateRequest,
    RoleTemplateResponse,
    StoreRolePolicyResponse,
    UserPermissionOverridePatchRequest,
    UserPermissionOverrideResponse,
)
from app.aris3.services.access_control import AccessControlService
from app.aris3.services.access_control_policies import AccessControlPolicyService
from app.aris3.services.audit import AuditEventPayload, AuditService
from app.aris3.services.idempotency import IdempotencyService, extract_idempotency_key


router = APIRouter()
logger = logging.getLogger(__name__)


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


def _is_store_bound_actor(token_data) -> bool:
    role = (token_data.role or "").upper()
    return role in {"MANAGER", "USER"} and bool(token_data.store_id)


def _enforce_user_store_scope(token_data, user) -> None:
    if is_superadmin(token_data.role):
        return
    if token_data.store_id:
        user_store_id = str(user.store_id) if user.store_id else None
        if user_store_id != token_data.store_id:
            raise AppError(ErrorCatalog.STORE_SCOPE_MISMATCH)


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
        raise AppError(ErrorCatalog.PERMISSION_DENIED)
    if not is_superadmin(token_data.role):
        tenant_id = context.tenant_id or token_data.tenant_id
        role_repo = RoleTemplateRepository(db)
        role_permissions = set(role_repo.list_permissions_for_role(normalized, tenant_id))
        if not role_permissions and tenant_id is not None:
            role_permissions = set(role_repo.list_permissions_for_role(normalized, None))
        cache = getattr(request.state, "permission_cache", None)
        if cache is None:
            cache = {}
            request.state.permission_cache = cache
        service = AccessControlService(db, cache=cache)
        allowed = {d.key for d in service.build_effective_permissions(context, token_data) if d.allowed}
        if role_permissions and not role_permissions.issubset(allowed):
            raise AppError(
                ErrorCatalog.PERMISSION_DENIED,
                details={
                    "message": "Role ceiling exceeded",
                    "missing": sorted(role_permissions.difference(allowed)),
                },
            )
    return normalized


def _count_query(db, stmt) -> int:
    return int(db.execute(stmt).scalar_one() or 0)


def _store_dependency_counts(db, *, store_id: str) -> dict[str, int]:
    return {
        "users": _count_query(db, select(func.count()).select_from(User).where(User.store_id == store_id)),
        "transfers": _count_query(
            db,
            select(func.count()).select_from(Transfer).where(
                or_(Transfer.origin_store_id == store_id, Transfer.destination_store_id == store_id)
            ),
        ),
        "store_role_policies": _count_query(
            db,
            select(func.count()).select_from(StoreRolePolicy).where(StoreRolePolicy.store_id == store_id),
        ),
        "sales": _count_query(db, select(func.count()).select_from(PosSale).where(PosSale.store_id == store_id)),
        "returns": _count_query(
            db,
            select(func.count()).select_from(PosReturnEvent).where(PosReturnEvent.store_id == store_id),
        ),
        "cash_sessions": _count_query(
            db,
            select(func.count()).select_from(PosCashSession).where(PosCashSession.store_id == store_id),
        ),
        "cash_movements": _count_query(
            db,
            select(func.count()).select_from(PosCashMovement).where(PosCashMovement.store_id == store_id),
        ),
        "cash_day_closes": _count_query(
            db,
            select(func.count()).select_from(PosCashDayClose).where(PosCashDayClose.store_id == store_id),
        ),
        "exports": _count_query(
            db,
            select(func.count()).select_from(ExportRecord).where(ExportRecord.store_id == store_id),
        ),
    }


def _tenant_dependency_counts(db, *, tenant_id: str) -> dict[str, int]:
    return {
        "stores": _count_query(db, select(func.count()).select_from(Store).where(Store.tenant_id == tenant_id)),
        "users": _count_query(db, select(func.count()).select_from(User).where(User.tenant_id == tenant_id)),
        "stock_items": _count_query(
            db,
            select(func.count()).select_from(StockItem).where(StockItem.tenant_id == tenant_id),
        ),
        "transfers": _count_query(
            db,
            select(func.count()).select_from(Transfer).where(Transfer.tenant_id == tenant_id),
        ),
        "transfer_lines": _count_query(
            db,
            select(func.count()).select_from(TransferLine).where(TransferLine.tenant_id == tenant_id),
        ),
        "transfer_movements": _count_query(
            db,
            select(func.count()).select_from(TransferMovement).where(TransferMovement.tenant_id == tenant_id),
        ),
        "sales": _count_query(db, select(func.count()).select_from(PosSale).where(PosSale.tenant_id == tenant_id)),
        "sale_lines": _count_query(
            db,
            select(func.count()).select_from(PosSaleLine).where(PosSaleLine.tenant_id == tenant_id),
        ),
        "returns": _count_query(
            db,
            select(func.count()).select_from(PosReturnEvent).where(PosReturnEvent.tenant_id == tenant_id),
        ),
        "payments": _count_query(
            db,
            select(func.count()).select_from(PosPayment).where(PosPayment.tenant_id == tenant_id),
        ),
        "cash_sessions": _count_query(
            db,
            select(func.count()).select_from(PosCashSession).where(PosCashSession.tenant_id == tenant_id),
        ),
        "cash_movements": _count_query(
            db,
            select(func.count()).select_from(PosCashMovement).where(PosCashMovement.tenant_id == tenant_id),
        ),
        "cash_day_closes": _count_query(
            db,
            select(func.count()).select_from(PosCashDayClose).where(PosCashDayClose.tenant_id == tenant_id),
        ),
        "exports": _count_query(
            db,
            select(func.count()).select_from(ExportRecord).where(ExportRecord.tenant_id == tenant_id),
        ),
        "tenant_role_policies": _count_query(
            db,
            select(func.count()).select_from(TenantRolePolicy).where(TenantRolePolicy.tenant_id == tenant_id),
        ),
        "store_role_policies": _count_query(
            db,
            select(func.count()).select_from(StoreRolePolicy).where(StoreRolePolicy.tenant_id == tenant_id),
        ),
        "user_permission_overrides": _count_query(
            db,
            select(func.count()).select_from(UserPermissionOverride).where(UserPermissionOverride.tenant_id == tenant_id),
        ),
    }


@router.get("/access-control/permission-catalog", response_model=PermissionCatalogResponse)
async def admin_permission_catalog(
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


@router.get("/access-control/role-templates/{role_name}", response_model=RoleTemplateResponse)
async def admin_get_role_template(
    request: Request,
    role_name: str,
    token_data=Depends(get_current_token_data),
    _current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    _require_admin(token_data)
    service = AccessControlPolicyService(db)
    snapshot = service.get_role_template(tenant_id=None, role_name=role_name.upper())
    return RoleTemplateResponse(
        role=role_name.upper(),
        permissions=snapshot.permissions,
        trace_id=getattr(request.state, "trace_id", ""),
    )


@router.put("/access-control/role-templates/{role_name}", response_model=RoleTemplateResponse)
async def admin_replace_role_template(
    request: Request,
    role_name: str,
    payload: RoleTemplateRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    _require_superadmin(token_data)
    _require_transaction_id(payload.transaction_id)
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

    service = AccessControlPolicyService(db)
    before, after = service.replace_role_template_permissions(
        tenant_id=None,
        role_name=role_name.upper(),
        permissions=payload.permissions,
    )
    response = RoleTemplateResponse(
        role=role_name.upper(),
        permissions=after.permissions,
        trace_id=getattr(request.state, "trace_id", ""),
    )
    context.record_success(status_code=200, response_body=response.model_dump())
    AuditService(db).record_event(
        AuditEventPayload(
            tenant_id=token_data.tenant_id or "platform",
            user_id=str(current_user.id),
            store_id=str(current_user.store_id) if current_user.store_id else None,
            trace_id=getattr(request.state, "trace_id", "") or None,
            actor=current_user.username,
            actor_role=current_user.role,
            action="access_control.role_template.update",
            entity_type="role_template",
            entity_id=f"platform:{role_name.upper()}",
            before={"permissions": before.permissions},
            after={"permissions": after.permissions},
            metadata={"role": role_name.upper(), "transaction_id": payload.transaction_id},
            result="success",
        )
    )
    return response


def _default_return_policy_payload() -> dict:
    return {
        "return_window_days": 30,
        "require_receipt": True,
        "allow_refund_cash": True,
        "allow_refund_card": True,
        "allow_refund_transfer": True,
        "allow_exchange": True,
        "require_manager_for_exceptions": False,
        "accepted_conditions": ["NEW", "GOOD", "USED"],
        "non_reusable_label_strategy": "ASSIGN_NEW_EPC",
        "restocking_fee_pct": 0.0,
    }


def _return_policy_response(settings: ReturnPolicySettings | None, trace_id: str) -> ReturnPolicySettingsResponse:
    if settings is None:
        data = _default_return_policy_payload()
    else:
        data = {
            "return_window_days": settings.return_window_days,
            "require_receipt": settings.require_receipt,
            "allow_refund_cash": settings.allow_refund_cash,
            "allow_refund_card": settings.allow_refund_card,
            "allow_refund_transfer": settings.allow_refund_transfer,
            "allow_exchange": settings.allow_exchange,
            "require_manager_for_exceptions": settings.require_manager_for_exceptions,
            "accepted_conditions": settings.accepted_conditions or [],
            "non_reusable_label_strategy": settings.non_reusable_label_strategy,
            "restocking_fee_pct": settings.restocking_fee_pct,
        }
    return ReturnPolicySettingsResponse(**data, trace_id=trace_id)


@router.get("/settings/return-policy", response_model=ReturnPolicySettingsResponse)
async def get_return_policy(
    request: Request,
    token_data=Depends(get_current_token_data),
    _current_user=Depends(require_active_user),
    _permission=Depends(require_permission("TENANT_VIEW")),
    db=Depends(get_db),
):
    tenant_id = _tenant_id_or_error(token_data)
    settings = ReturnPolicySettingsRepository(db).get_by_tenant_id(tenant_id)
    return _return_policy_response(settings, getattr(request.state, "trace_id", ""))


@router.patch("/settings/return-policy", response_model=ReturnPolicySettingsResponse)
async def patch_return_policy(
    request: Request,
    payload: ReturnPolicySettingsPatchRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    _permission=Depends(require_permission("SETTINGS_MANAGE")),
    db=Depends(get_db),
):
    tenant_id = _tenant_id_or_error(token_data)
    if all(
        value is None
        for value in [
            payload.return_window_days,
            payload.require_receipt,
            payload.allow_refund_cash,
            payload.allow_refund_card,
            payload.allow_refund_transfer,
            payload.allow_exchange,
            payload.require_manager_for_exceptions,
            payload.accepted_conditions,
            payload.non_reusable_label_strategy,
            payload.restocking_fee_pct,
        ]
    ):
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

    repo = ReturnPolicySettingsRepository(db)
    settings = repo.get_by_tenant_id(tenant_id)
    before = None
    if settings is None:
        defaults = _default_return_policy_payload()
        settings = ReturnPolicySettings(
            tenant_id=tenant_id,
            return_window_days=payload.return_window_days
            if payload.return_window_days is not None
            else defaults["return_window_days"],
            require_receipt=payload.require_receipt
            if payload.require_receipt is not None
            else defaults["require_receipt"],
            allow_refund_cash=payload.allow_refund_cash
            if payload.allow_refund_cash is not None
            else defaults["allow_refund_cash"],
            allow_refund_card=payload.allow_refund_card
            if payload.allow_refund_card is not None
            else defaults["allow_refund_card"],
            allow_refund_transfer=payload.allow_refund_transfer
            if payload.allow_refund_transfer is not None
            else defaults["allow_refund_transfer"],
            allow_exchange=payload.allow_exchange if payload.allow_exchange is not None else defaults["allow_exchange"],
            require_manager_for_exceptions=payload.require_manager_for_exceptions
            if payload.require_manager_for_exceptions is not None
            else defaults["require_manager_for_exceptions"],
            accepted_conditions=payload.accepted_conditions or defaults["accepted_conditions"],
            non_reusable_label_strategy=payload.non_reusable_label_strategy
            if payload.non_reusable_label_strategy is not None
            else defaults["non_reusable_label_strategy"],
            restocking_fee_pct=payload.restocking_fee_pct
            if payload.restocking_fee_pct is not None
            else defaults["restocking_fee_pct"],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        repo.create(settings)
    else:
        before = {
            "return_window_days": settings.return_window_days,
            "require_receipt": settings.require_receipt,
            "allow_refund_cash": settings.allow_refund_cash,
            "allow_refund_card": settings.allow_refund_card,
            "allow_refund_transfer": settings.allow_refund_transfer,
            "allow_exchange": settings.allow_exchange,
            "require_manager_for_exceptions": settings.require_manager_for_exceptions,
            "accepted_conditions": settings.accepted_conditions,
            "non_reusable_label_strategy": settings.non_reusable_label_strategy,
            "restocking_fee_pct": settings.restocking_fee_pct,
        }
        if payload.return_window_days is not None:
            settings.return_window_days = payload.return_window_days
        if payload.require_receipt is not None:
            settings.require_receipt = payload.require_receipt
        if payload.allow_refund_cash is not None:
            settings.allow_refund_cash = payload.allow_refund_cash
        if payload.allow_refund_card is not None:
            settings.allow_refund_card = payload.allow_refund_card
        if payload.allow_refund_transfer is not None:
            settings.allow_refund_transfer = payload.allow_refund_transfer
        if payload.allow_exchange is not None:
            settings.allow_exchange = payload.allow_exchange
        if payload.require_manager_for_exceptions is not None:
            settings.require_manager_for_exceptions = payload.require_manager_for_exceptions
        if payload.accepted_conditions is not None:
            settings.accepted_conditions = payload.accepted_conditions
        if payload.non_reusable_label_strategy is not None:
            settings.non_reusable_label_strategy = payload.non_reusable_label_strategy
        if payload.restocking_fee_pct is not None:
            settings.restocking_fee_pct = payload.restocking_fee_pct
        settings.updated_at = datetime.utcnow()
        repo.update(settings)

    response = _return_policy_response(settings, getattr(request.state, "trace_id", ""))
    context_idempotency.record_success(status_code=200, response_body=response.model_dump())

    AuditService(db).record_event(
        AuditEventPayload(
            tenant_id=tenant_id,
            user_id=str(current_user.id),
            store_id=str(current_user.store_id) if current_user.store_id else None,
            trace_id=getattr(request.state, "trace_id", "") or None,
            actor=current_user.username,
            actor_role=current_user.role,
            action="admin.settings.return_policy.update",
            entity_type="return_policy_settings",
            entity_id=str(settings.id),
            before=before,
            after={
                "return_window_days": settings.return_window_days,
                "require_receipt": settings.require_receipt,
                "allow_refund_cash": settings.allow_refund_cash,
                "allow_refund_card": settings.allow_refund_card,
                "allow_refund_transfer": settings.allow_refund_transfer,
                "allow_exchange": settings.allow_exchange,
                "require_manager_for_exceptions": settings.require_manager_for_exceptions,
                "accepted_conditions": settings.accepted_conditions,
                "non_reusable_label_strategy": settings.non_reusable_label_strategy,
                "restocking_fee_pct": settings.restocking_fee_pct,
            },
            metadata=None,
            result="success",
        )
    )
    return response


@router.get("/access-control/tenant-role-policies/{role_name}", response_model=RolePolicyResponse)
async def admin_get_tenant_role_policy(
    request: Request,
    role_name: str,
    token_data=Depends(get_current_token_data),
    _current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    _require_admin(token_data)
    tenant_id = _tenant_id_or_error(token_data)
    service = AccessControlPolicyService(db)
    snapshot = service.get_tenant_role_policy(tenant_id=tenant_id, role_name=role_name.upper())
    return RolePolicyResponse(
        tenant_id=tenant_id,
        role=role_name.upper(),
        allow=snapshot.allow,
        deny=snapshot.deny,
        trace_id=getattr(request.state, "trace_id", ""),
    )


@router.put("/access-control/tenant-role-policies/{role_name}", response_model=RolePolicyResponse)
async def admin_replace_tenant_role_policy(
    request: Request,
    role_name: str,
    payload: RolePolicyRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    _require_admin(token_data)
    tenant_id = _tenant_id_or_error(token_data)
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
            actor_role=current_user.role,
            action="access_control.tenant_role_policy.update",
            entity_type="role_policy",
            entity_id=f"{tenant_id}:{role_name.upper()}",
            before={"allow": before.allow, "deny": before.deny},
            after={"allow": after.allow, "deny": after.deny},
            metadata={"role": role_name.upper(), "transaction_id": payload.transaction_id},
            result="success",
        )
    )
    return response


@router.get(
    "/access-control/store-role-policies/{store_id}/{role_name}",
    response_model=StoreRolePolicyResponse,
)
async def admin_get_store_role_policy(
    request: Request,
    store_id: str,
    role_name: str,
    token_data=Depends(get_current_token_data),
    _current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    _require_admin(token_data)
    tenant_id = _tenant_id_or_error(token_data)
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
    "/access-control/store-role-policies/{store_id}/{role_name}",
    response_model=StoreRolePolicyResponse,
)
async def admin_replace_store_role_policy(
    request: Request,
    store_id: str,
    role_name: str,
    payload: RolePolicyRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    _require_admin(token_data)
    tenant_id = _tenant_id_or_error(token_data)
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
            actor_role=current_user.role,
            action="access_control.store_role_policy.update",
            entity_type="role_policy",
            entity_id=f"{tenant_id}:{store_id}:{role_name.upper()}",
            before={"allow": before.allow, "deny": before.deny},
            after={"allow": after.allow, "deny": after.deny},
            metadata={
                "role": role_name.upper(),
                "store_id": store_id,
                "transaction_id": payload.transaction_id,
            },
            result="success",
        )
    )
    return response


@router.get("/access-control/user-overrides/{user_id}", response_model=UserPermissionOverrideResponse)
async def admin_get_user_overrides(
    request: Request,
    user_id: str,
    token_data=Depends(get_current_token_data),
    _current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    _require_admin(token_data)
    tenant_id = _tenant_id_or_error(token_data)
    user = UserRepository(db).get_by_id_in_tenant(user_id, tenant_id)
    if user is None:
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


@router.patch("/access-control/user-overrides/{user_id}", response_model=UserPermissionOverrideResponse)
async def admin_patch_user_overrides(
    request: Request,
    user_id: str,
    payload: UserPermissionOverridePatchRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    _require_admin(token_data)
    tenant_id = _tenant_id_or_error(token_data)
    user = UserRepository(db).get_by_id_in_tenant(user_id, tenant_id)
    if user is None:
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
    before = service.get_user_overrides(tenant_id=tenant_id, user_id=user_id)
    allow = before.allow if payload.allow is None else payload.allow
    deny = before.deny if payload.deny is None else payload.deny
    _, after = service.replace_user_overrides(
        tenant_id=tenant_id,
        user_id=user_id,
        allow=allow,
        deny=deny,
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
            actor_role=current_user.role,
            action="access_control.user_override.update",
            entity_type="user_override",
            entity_id=f"{tenant_id}:{user_id}",
            before={"allow": before.allow, "deny": before.deny},
            after={"allow": after.allow, "deny": after.deny},
            metadata={"user_id": user_id, "transaction_id": payload.transaction_id},
            result="success",
        )
    )
    return response


@router.get("/access-control/effective-permissions", response_model=EffectivePermissionsResponse)
async def admin_effective_permissions(
    request: Request,
    user_id: str,
    store_id: str | None = None,
    token_data=Depends(get_current_token_data),
    _current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    _require_admin(token_data)
    tenant_id = _tenant_id_or_error(token_data)
    user = UserRepository(db).get_by_id_in_tenant(user_id, tenant_id)
    if user is None:
        raise AppError(ErrorCatalog.CROSS_TENANT_ACCESS_DENIED)
    _enforce_user_store_scope(token_data, user)
    if store_id and user.store_id and str(user.store_id) != store_id:
        raise AppError(ErrorCatalog.STORE_SCOPE_MISMATCH)

    target_store_id = store_id or (str(user.store_id) if user.store_id else None)
    if target_store_id:
        store = enforce_store_scope(
            token_data,
            target_store_id,
            db,
            allow_superadmin=True,
            broader_store_roles={"SUPERADMIN"},
        )
        if str(store.tenant_id) != tenant_id:
            raise AppError(ErrorCatalog.STORE_SCOPE_MISMATCH)

    cache = getattr(request.state, "permission_cache", None)
    if cache is None:
        cache = {}
        request.state.permission_cache = cache
    service = AccessControlService(db, cache=cache)
    context = build_request_context(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        store_id=target_store_id,
        role=user.role,
        trace_id=getattr(request.state, "trace_id", ""),
    )
    decisions, trace = service.build_effective_permissions_with_trace(context, None)
    denies_applied = sorted(
        {entry.key for entry in decisions if entry.source in {"explicit_deny", "user_override_deny", "store_policy_deny", "tenant_policy_deny"}}
    )
    return EffectivePermissionsResponse(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        store_id=target_store_id,
        role=user.role,
        permissions=[PermissionEntry(key=d.key, allowed=d.allowed, source=d.source) for d in decisions],
        subject=EffectivePermissionSubject(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            store_id=target_store_id,
            role=user.role,
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
            actor_role=current_user.role,
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
            actor_role=current_user.role,
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


@router.delete(
    "/tenants/{tenant_id}",
    response_model=AdminDeleteResponse,
    responses={
        404: {"description": "Tenant not found", "content": {"application/json": {"example": {"code": "HTTP_ERROR", "message": "Tenant not found", "details": None, "trace_id": "trace-123"}}}},
        409: {"description": "Tenant has dependencies", "model": AdminDeleteConflictResponse, "content": {"application/json": {"example": {"message": "Cannot delete tenant with active dependencies", "dependencies": {"stores": 2, "users": 7}, "trace_id": "trace-123"}}}},
        422: {"description": "Validation error", "content": {"application/json": {"example": {"code": "VALIDATION_ERROR", "message": "Validation error", "details": {"field": "tenant_id"}, "trace_id": "trace-123"}}}},
    },
)
async def delete_tenant(
    request: Request,
    tenant_id: str,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    _require_superadmin(token_data)
    idempotency_key = extract_idempotency_key(request.headers, required=True)
    request_hash = IdempotencyService.fingerprint({"tenant_id": tenant_id})
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

    tenant = TenantRepository(db).get_by_id(tenant_id)
    if tenant is None:
        payload = {"message": "Tenant not found", "trace_id": getattr(request.state, "trace_id", "")}
        context.record_failure(status_code=404, response_body=payload)
        return JSONResponse(status_code=404, content=payload)

    dependencies = {name: count for name, count in _tenant_dependency_counts(db, tenant_id=tenant_id).items() if count > 0}
    if dependencies:
        payload = {
            "message": "Cannot delete tenant with active dependencies",
            "dependencies": dependencies,
            "trace_id": getattr(request.state, "trace_id", ""),
        }
        context.record_failure(status_code=409, response_body=payload)
        return JSONResponse(status_code=409, content=payload)

    db.delete(tenant)
    db.commit()

    response = AdminDeleteResponse(
        resource="tenant",
        resource_id=tenant_id,
        deleted=True,
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
            actor_role=current_user.role,
            action="admin.tenant.delete",
            entity_type="tenant",
            entity_id=tenant_id,
            before={"name": tenant.name, "status": tenant.status},
            after=None,
            metadata={"hard_delete": True, "dependencies_checked": True},
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
            actor_role=current_user.role,
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


@router.post(
    "/stores",
    response_model=StoreResponse,
    status_code=201,
    summary="Create store",
    description=(
        "Creates a store in a tenant scope. `tenant_id` in the request body is the canonical tenant source. "
        "For legacy compatibility, `query_tenant_id` query param is also accepted. "
        "SUPERADMIN/PLATFORM_ADMIN must provide tenant explicitly (no default-tenant fallback). "
        "If body and query tenant are both present they must match."
    ),
)
async def create_store(
    request: Request,
    payload: StoreCreateRequest,
    query_tenant_id: str | None = Query(
        default=None,
        description="Legacy tenant selector for compatibility. Prefer body.tenant_id.",
    ),
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    _permission=Depends(require_permission("STORE_MANAGE")),
    db=Depends(get_db),
):
    token_tenant_id = _tenant_id_or_error(token_data)
    body_tenant_id = payload.tenant_id
    legacy_tenant_id = request.query_params.get("tenant_id")
    query_tenant_candidate = query_tenant_id or legacy_tenant_id

    if body_tenant_id and query_tenant_candidate and body_tenant_id != query_tenant_candidate:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={
                "message": "tenant_id mismatch between body and query_tenant_id",
                "body_tenant_id": body_tenant_id,
                "query_tenant_id": query_tenant_candidate,
            },
        )

    request_tenant_id = body_tenant_id or query_tenant_candidate
    user_role = (current_user.role or "").upper()

    if user_role in {"SUPERADMIN", "PLATFORM_ADMIN"}:
        if not request_tenant_id:
            raise AppError(
                ErrorCatalog.TENANT_ID_REQUIRED_FOR_SUPERADMIN,
                details={
                    "message": "tenant_id is required in body or query_tenant_id",
                },
            )
        if TenantRepository(db).get_by_id(request_tenant_id) is None:
            raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "Tenant not found"})
        resolved_tenant_id = request_tenant_id
    else:
        if request_tenant_id and request_tenant_id != token_tenant_id:
            raise AppError(ErrorCatalog.CROSS_TENANT_ACCESS_DENIED)
        resolved_tenant_id = token_tenant_id

    logger.debug(
        "Resolved tenant for admin store creation",
        extra={
            "user_role": current_user.role,
            "token_tenant_id": token_tenant_id,
            "request_tenant_id": request_tenant_id,
            "resolved_tenant_id": resolved_tenant_id,
        },
    )

    idempotency_key = extract_idempotency_key(request.headers, required=True)
    request_hash = IdempotencyService.fingerprint(payload.model_dump(mode="json"))
    idempotency_service = IdempotencyService(db)
    context, replay = idempotency_service.start(
        tenant_id=resolved_tenant_id,
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
    store = repo.create(Store(tenant_id=resolved_tenant_id, name=payload.name))

    response = StoreResponse(
        store=_store_item(store),
        trace_id=getattr(request.state, "trace_id", ""),
    )
    context.record_success(status_code=201, response_body=response.model_dump(mode="json"))

    AuditService(db).record_event(
        AuditEventPayload(
            tenant_id=resolved_tenant_id,
            user_id=str(current_user.id),
            store_id=str(current_user.store_id) if current_user.store_id else None,
            trace_id=getattr(request.state, "trace_id", "") or None,
            actor=current_user.username,
            actor_role=current_user.role,
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
    store = StoreRepository(db).get_by_id_in_tenant(store_id, tenant_id)
    if store is None:
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
    store = StoreRepository(db).get_by_id_in_tenant(store_id, tenant_id)
    if store is None:
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
            actor_role=current_user.role,
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


@router.delete(
    "/stores/{store_id}",
    response_model=AdminDeleteResponse,
    responses={
        200: {
            "description": "Store deleted",
            "content": {
                "application/json": {
                    "example": {
                        "resource": "store",
                        "resource_id": "5f0f8f36-b064-4b4f-bf95-df6034eb9a64",
                        "deleted": True,
                        "trace_id": "trace-123",
                    }
                }
            },
        },
        404: {"description": "Store not found", "content": {"application/json": {"example": {"code": "HTTP_ERROR", "message": "Store not found", "details": None, "trace_id": "trace-123"}}}},
        409: {"description": "Store has dependencies", "model": AdminDeleteConflictResponse, "content": {"application/json": {"example": {"message": "Cannot delete store with active dependencies", "dependencies": {"users": 3, "sales": 18}, "trace_id": "trace-123"}}}},
        422: {"description": "Validation error", "content": {"application/json": {"example": {"code": "VALIDATION_ERROR", "message": "Validation error", "details": {"field": "store_id"}, "trace_id": "trace-123"}}}},
    },
)
async def delete_store(
    request: Request,
    store_id: str,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    _require_superadmin(token_data)
    idempotency_key = extract_idempotency_key(request.headers, required=True)
    request_hash = IdempotencyService.fingerprint({"store_id": store_id})
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

    store = StoreRepository(db).get_by_id(store_id)
    if store is None:
        payload = {"message": "Store not found", "trace_id": getattr(request.state, "trace_id", "")}
        context.record_failure(status_code=404, response_body=payload)
        return JSONResponse(status_code=404, content=payload)

    dependencies = {name: count for name, count in _store_dependency_counts(db, store_id=store_id).items() if count > 0}
    if dependencies:
        payload = {
            "message": "Cannot delete store with active dependencies",
            "dependencies": dependencies,
            "trace_id": getattr(request.state, "trace_id", ""),
        }
        context.record_failure(status_code=409, response_body=payload)
        return JSONResponse(status_code=409, content=payload)

    db.delete(store)
    db.commit()

    response = AdminDeleteResponse(
        resource="store",
        resource_id=store_id,
        deleted=True,
        trace_id=getattr(request.state, "trace_id", ""),
    )
    context.record_success(status_code=200, response_body=response.model_dump(mode="json"))

    AuditService(db).record_event(
        AuditEventPayload(
            tenant_id=str(store.tenant_id),
            user_id=str(current_user.id),
            store_id=str(current_user.store_id) if current_user.store_id else None,
            trace_id=getattr(request.state, "trace_id", "") or None,
            actor=current_user.username,
            actor_role=current_user.role,
            action="admin.store.delete",
            entity_type="store",
            entity_id=store_id,
            before={"name": store.name, "tenant_id": str(store.tenant_id)},
            after=None,
            metadata={"hard_delete": True, "dependencies_checked": True},
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
    store_id = token_data.store_id if _is_store_bound_actor(token_data) else None
    users = UserRepository(db).list_by_tenant(tenant_id, store_id=store_id)
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
            raise AppError(ErrorCatalog.TENANT_STORE_MISMATCH)

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
            actor_role=current_user.role,
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
    user = UserRepository(db).get_by_id_in_tenant(user_id, tenant_id)
    if user is None:
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
    user = UserRepository(db).get_by_id_in_tenant(user_id, tenant_id)
    if user is None:
        raise AppError(ErrorCatalog.CROSS_TENANT_ACCESS_DENIED)

    if payload.username is None and payload.email is None and payload.store_id is None:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "At least one field must be provided"},
        )

    if payload.store_id:
        store = StoreRepository(db).get_by_id_in_tenant(payload.store_id, tenant_id)
        if store is None:
            raise AppError(ErrorCatalog.TENANT_STORE_MISMATCH)

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
            actor_role=current_user.role,
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


@router.delete(
    "/users/{user_id}",
    response_model=AdminDeleteResponse,
    responses={
        200: {
            "description": "User deleted",
            "content": {
                "application/json": {
                    "example": {
                        "resource": "user",
                        "resource_id": "9490f159-4054-4f8f-bf5a-5b5cad32e5d9",
                        "deleted": True,
                        "trace_id": "trace-123",
                    }
                }
            },
        },
        404: {"description": "User not found", "content": {"application/json": {"example": {"code": "HTTP_ERROR", "message": "User not found", "details": None, "trace_id": "trace-123"}}}},
        409: {"description": "User has critical dependencies", "model": AdminDeleteConflictResponse, "content": {"application/json": {"example": {"message": "Cannot delete user with critical dependencies", "dependencies": {"transfers": 2}, "trace_id": "trace-123"}}}},
        422: {"description": "Validation error", "content": {"application/json": {"example": {"code": "VALIDATION_ERROR", "message": "Validation error", "details": {"field": "user_id"}, "trace_id": "trace-123"}}}},
    },
)
async def delete_user(
    request: Request,
    user_id: str,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    _require_superadmin(token_data)
    idempotency_key = extract_idempotency_key(request.headers, required=True)
    request_hash = IdempotencyService.fingerprint({"user_id": user_id})
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

    user = UserRepository(db).get_by_id(user_id)
    if user is None:
        payload = {"message": "User not found", "trace_id": getattr(request.state, "trace_id", "")}
        context.record_failure(status_code=404, response_body=payload)
        return JSONResponse(status_code=404, content=payload)

    transfer_dependencies = _count_query(
        db,
        select(func.count()).select_from(Transfer).where(
            or_(
                Transfer.created_by_user_id == user_id,
                Transfer.updated_by_user_id == user_id,
                Transfer.dispatched_by_user_id == user_id,
                Transfer.canceled_by_user_id == user_id,
            )
        ),
    )
    if transfer_dependencies > 0:
        payload = {
            "message": "Cannot delete user with critical dependencies",
            "dependencies": {"transfers": transfer_dependencies},
            "trace_id": getattr(request.state, "trace_id", ""),
        }
        context.record_failure(status_code=409, response_body=payload)
        return JSONResponse(status_code=409, content=payload)

    db.query(UserPermissionOverride).filter(UserPermissionOverride.user_id == user_id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()

    response = AdminDeleteResponse(
        resource="user",
        resource_id=user_id,
        deleted=True,
        trace_id=getattr(request.state, "trace_id", ""),
    )
    context.record_success(status_code=200, response_body=response.model_dump(mode="json"))

    AuditService(db).record_event(
        AuditEventPayload(
            tenant_id=str(user.tenant_id),
            user_id=str(current_user.id),
            store_id=str(current_user.store_id) if current_user.store_id else None,
            trace_id=getattr(request.state, "trace_id", "") or None,
            actor=current_user.username,
            actor_role=current_user.role,
            action="admin.user.delete",
            entity_type="user",
            entity_id=user_id,
            before={"username": user.username, "email": user.email, "role": user.role},
            after=None,
            metadata={"hard_delete": True, "dependencies_checked": ["transfers"]},
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
    user_repo = UserRepository(db)
    if is_superadmin(token_data.role):
        user = user_repo.get_by_id(user_id)
        if user is None:
            raise AppError(ErrorCatalog.CROSS_TENANT_ACCESS_DENIED)
        tenant_id = str(user.tenant_id)
    else:
        tenant_id = _tenant_id_or_error(token_data)
        user = user_repo.get_by_id_in_tenant(user_id, tenant_id)
        if user is None:
            raise AppError(ErrorCatalog.CROSS_TENANT_ACCESS_DENIED)
        if _is_store_bound_actor(token_data):
            _enforce_user_store_scope(token_data, user)

    if not payload.transaction_id:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={"message": "transaction_id is required"},
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
            actor_role=current_user.role,
            action=f"admin.user.{action}",
            entity_type="user",
            entity_id=str(user.id),
            before=before,
            after={
                "status": user.status,
                "role": user.role,
                "must_change_password": user.must_change_password,
            },
            metadata={
                "temporary_password_set": temporary_password is not None,
                "target_user_id": str(user.id),
                "transaction_id": payload.transaction_id,
            },
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
            actor_role=current_user.role,
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
