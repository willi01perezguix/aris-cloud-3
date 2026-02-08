from typing import Iterable

from sqlalchemy import select

from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.core.security import TokenData
from app.aris3.db.models import Store


SUPERADMIN_ROLES = {"SUPERADMIN", "PLATFORM_ADMIN"}
DEFAULT_BROAD_STORE_ROLES = {"SUPERADMIN", "ADMIN"}


def _normalize_role(role: str | None) -> str:
    return (role or "").upper()


def is_superadmin(role: str | None) -> bool:
    return _normalize_role(role) in SUPERADMIN_ROLES


def enforce_tenant_scope(
    token_data: TokenData,
    tenant_id: str | None,
    *,
    allow_superadmin: bool = False,
) -> None:
    if not tenant_id or not token_data.tenant_id:
        raise AppError(ErrorCatalog.TENANT_SCOPE_REQUIRED)
    if token_data.tenant_id != tenant_id:
        if allow_superadmin and is_superadmin(token_data.role):
            return
        raise AppError(ErrorCatalog.CROSS_TENANT_ACCESS_DENIED)


def enforce_store_scope(
    token_data: TokenData,
    store_id: str | None,
    db,
    *,
    allow_superadmin: bool = False,
    broader_store_roles: Iterable[str] | None = None,
) -> Store:
    if not store_id:
        raise AppError(ErrorCatalog.STORE_SCOPE_REQUIRED)
    if not token_data.tenant_id:
        raise AppError(ErrorCatalog.TENANT_SCOPE_REQUIRED)

    store = db.execute(select(Store).where(Store.id == store_id)).scalars().first()
    if store is None:
        raise AppError(ErrorCatalog.STORE_SCOPE_MISMATCH)
    if store.tenant_id != token_data.tenant_id:
        if allow_superadmin and is_superadmin(token_data.role):
            return store
        raise AppError(ErrorCatalog.STORE_SCOPE_MISMATCH)

    if token_data.store_id:
        role = _normalize_role(token_data.role)
        allowed_roles = {r.upper() for r in (broader_store_roles or DEFAULT_BROAD_STORE_ROLES)}
        if role not in allowed_roles and token_data.store_id != store_id:
            raise AppError(ErrorCatalog.STORE_SCOPE_MISMATCH)
    return store
