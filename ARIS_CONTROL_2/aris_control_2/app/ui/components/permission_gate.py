from aris_control_2.app.domain.models.session_context import SessionContext
from aris_control_2.app.domain.policies.tenant_context_policy import TenantContextPolicy


class PermissionGate:
    @staticmethod
    def require_tenant_context(context: SessionContext) -> tuple[bool, str]:
        allowed, reason = TenantContextPolicy.can_access_tenant_scoped_resources(context)
        if allowed:
            return True, ""
        if reason == "TENANT_CONTEXT_REQUIRED":
            return False, "SUPERADMIN debe seleccionar tenant antes de operar Stores/Users."
        return False, "El token no incluye tenant_id para recursos tenant-scoped."

    @staticmethod
    def can(context: SessionContext, permission: str) -> bool:
        return context.can(permission)
