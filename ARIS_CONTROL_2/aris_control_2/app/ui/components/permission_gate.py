from aris_control_2.app.domain.models.session_context import SessionContext


class PermissionGate:
    @staticmethod
    def require_tenant_context(context: SessionContext) -> tuple[bool, str]:
        if context.effective_tenant_id:
            return True, ""
        return False, "Tenant context required. Select a tenant first."
