from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.infrastructure.sdk_adapter.admin_adapter import AdminAdapter
from aris_control_2.app.ui.components.error_banner import ErrorBanner
from aris_control_2.app.ui.components.permission_gate import PermissionGate


class UsersView:
    def __init__(self, adapter: AdminAdapter, state: SessionState) -> None:
        self.adapter = adapter
        self.state = state

    def render(self) -> None:
        allowed, reason = PermissionGate.require_tenant_context(self.state.context)
        if not allowed:
            ErrorBanner.show(reason)
            return
        users = self.adapter.list_users(self.state.context.effective_tenant_id)
        print("-- Users --")
        for user in users:
            print(f"{user.id} :: {user.email}")
