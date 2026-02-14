from dataclasses import dataclass

from aris_control_2.app.domain.models.session_context import SessionContext
from aris_control_2.app.domain.policies.tenant_context_policy import TenantContextPolicy


@dataclass(frozen=True)
class GateResult:
    allowed: bool
    reason: str = ""


class PermissionGate:
    @staticmethod
    def require_tenant_context(context: SessionContext) -> GateResult:
        allowed, reason = TenantContextPolicy.can_access_tenant_scoped_resources(context)
        if allowed:
            return GateResult(True)
        if reason == "TENANT_CONTEXT_REQUIRED":
            return GateResult(False, "SUPERADMIN debe seleccionar tenant antes de operar Stores/Users.")
        return GateResult(False, "El token no incluye tenant_id para recursos tenant-scoped.")

    @staticmethod
    def check(context: SessionContext, permission: str) -> GateResult:
        if context.can(permission):
            return GateResult(True)
        return GateResult(False, f"No tienes permiso para esta acción ({permission}).")
