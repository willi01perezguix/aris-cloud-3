import pytest

from aris_control_2.app.domain.models.session_context import SessionContext
from aris_control_2.app.domain.policies.tenant_context_policy import TenantContextPolicy
from aris_control_2.app.ui.components.permission_gate import PermissionGate
from aris_control_2.app.ui.views.users_view import build_sensitive_action_summary


@pytest.mark.parametrize(
    ("role", "token_tenant", "selected_tenant", "expected"),
    [
        ("SUPERADMIN", None, "tenant-selected", "tenant-selected"),
        ("ADMIN", "tenant-token", "tenant-selected", "tenant-token"),
        ("MANAGER", "tenant-token", None, "tenant-token"),
        ("USER", "tenant-token", "tenant-other", "tenant-token"),
    ],
)
def test_resolve_mutation_tenant_id_by_role(role: str, token_tenant: str | None, selected_tenant: str | None, expected: str) -> None:
    context = SessionContext(actor_role=role, token_tenant_id=token_tenant, selected_tenant_id=selected_tenant)

    tenant_id, reason = TenantContextPolicy.resolve_mutation_tenant_id(context)

    assert tenant_id == expected
    assert reason == ""


def test_block_mutation_without_required_tenant_context() -> None:
    context = SessionContext(actor_role="SUPERADMIN", token_tenant_id=None, selected_tenant_id=None)

    tenant_id, reason = TenantContextPolicy.resolve_mutation_tenant_id(context)

    assert tenant_id is None
    assert reason == "TENANT_CONTEXT_REQUIRED"


def test_permission_gate_reason_uses_required_copy() -> None:
    context = SessionContext(actor_role="MANAGER", effective_permissions=["users.view"])

    result = PermissionGate.check(context, "users.create")

    assert result.allowed is False
    assert "No tienes permiso para esta acción" in result.reason


def test_sensitive_action_summary_includes_scope_and_changes() -> None:
    summary = build_sensitive_action_summary("set_role", "user-1", {"role": "ADMIN"}, "tenant-1")

    assert "set_role" in summary
    assert "tenant-1" in summary
    assert "ADMIN" in summary
