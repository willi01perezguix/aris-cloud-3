from aris_control_2.app.domain.models.session_context import SessionContext
from aris_control_2.app.domain.policies.tenant_context_policy import TenantContextPolicy


def test_superadmin_without_selected_tenant_is_blocked() -> None:
    context = SessionContext(actor_role="SUPERADMIN", token_tenant_id=None, selected_tenant_id=None)

    allowed, reason = TenantContextPolicy.can_access_tenant_scoped_resources(context)

    assert allowed is False
    assert reason == "TENANT_CONTEXT_REQUIRED"


def test_tenant_scoped_uses_token_tenant_id() -> None:
    context = SessionContext(actor_role="ADMIN", token_tenant_id="tenant-a", selected_tenant_id="tenant-b")

    assert TenantContextPolicy.resolve_effective_tenant_id(context) == "tenant-a"
