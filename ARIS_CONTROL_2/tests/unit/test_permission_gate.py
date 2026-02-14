from aris_control_2.app.domain.models.session_context import SessionContext
from aris_control_2.app.ui.components.permission_gate import PermissionGate


def test_permission_gate_hides_disallowed_action() -> None:
    context = SessionContext(actor_role="ADMIN", token_tenant_id="tenant-a", effective_permissions=["users.view"])

    result = PermissionGate.check(context, "users.actions")

    assert not result.allowed
    assert "users.actions" in result.reason


def test_permission_gate_superadmin_requires_selected_tenant() -> None:
    context = SessionContext(actor_role="SUPERADMIN")
    context.refresh_effective_tenant()

    result = PermissionGate.require_tenant_context(context)

    assert not result.allowed
    assert "seleccionar tenant" in result.reason.lower()
