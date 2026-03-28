from __future__ import annotations

from dataclasses import dataclass

from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.db.models import Tenant
from app.aris3.repos.tenants import TenantRepository


ACTIVE_STATUS = "ACTIVE"
@dataclass(frozen=True)
class ActiveStateEvaluation:
    allowed: bool
    reason: str | None = None


def normalize_status(value: str | None) -> str:
    return (value or "").strip().upper()


def is_status_active(value: str | None) -> bool:
    return normalize_status(value) == ACTIVE_STATUS


def is_tenant_active(tenant: Tenant | None) -> bool:
    if tenant is None:
        return False
    return normalize_status(tenant.status) == ACTIVE_STATUS


def evaluate_auth_eligibility(*, user, tenant: Tenant | None) -> ActiveStateEvaluation:
    if user is None:
        return ActiveStateEvaluation(False, "missing_user")
    if not bool(user.is_active):
        return ActiveStateEvaluation(False, "user_is_active_false")
    if not is_status_active(user.status):
        return ActiveStateEvaluation(False, "user_status_not_active")
    if not is_tenant_active(tenant):
        return ActiveStateEvaluation(False, "tenant_inactive")
    return ActiveStateEvaluation(True)


def ensure_user_can_authenticate(*, db, user) -> None:
    tenant = TenantRepository(db).get_by_id(str(user.tenant_id)) if user is not None and user.tenant_id else None
    evaluation = evaluate_auth_eligibility(user=user, tenant=tenant)
    if not evaluation.allowed:
        raise AppError(ErrorCatalog.USER_INACTIVE)
