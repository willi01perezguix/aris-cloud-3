from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.ui.components.permission_gate import PermissionGate


def test_users_actions_hidden_when_permission_missing() -> None:
    state = SessionState()
    state.context.actor_role = "ADMIN"
    state.context.token_tenant_id = "tenant-a"
    state.context.refresh_effective_tenant()
    state.context.effective_permissions = ["users.view"]

    gate = PermissionGate.check(state.context, "users.actions")

    assert not gate.allowed
