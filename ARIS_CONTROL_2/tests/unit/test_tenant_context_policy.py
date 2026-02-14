from aris_control_2.app.domain.models.session_context import SessionContext
from aris_control_2.app.domain.policies.tenant_context_policy import TenantContextPolicy


def test_superadmin_requires_selected_tenant_for_effective_context() -> None:
    context = SessionContext(actor_role="SUPERADMIN", token_tenant_id=None, selected_tenant_id=None)

    assert TenantContextPolicy.resolve_effective_tenant_id(context) is None


def test_tenant_scoped_uses_token_tenant_id() -> None:
    context = SessionContext(actor_role="ADMIN", token_tenant_id="tenant-a", selected_tenant_id="tenant-b")

    assert TenantContextPolicy.resolve_effective_tenant_id(context) == "tenant-a"
