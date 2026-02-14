from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.infrastructure.sdk_adapter.auth_adapter import AuthAdapter


class LoadMeUseCase:
    def __init__(self, auth_adapter: AuthAdapter, state: SessionState) -> None:
        self.auth_adapter = auth_adapter
        self.state = state

    def execute(self) -> None:
        me = self.auth_adapter.me()
        self.state.context.actor_role = me.get("role", self.state.context.actor_role)
        self.state.context.token_tenant_id = me.get("tenant_id", self.state.context.token_tenant_id)
        if self.state.context.actor_role != "SUPERADMIN":
            self.state.context.selected_tenant_id = self.state.context.token_tenant_id
        self.state.context.effective_permissions = me.get("permissions", [])
        self.state.context.must_change_password = bool(
            me.get("must_change_password", self.state.context.must_change_password)
        )
        self.state.context.refresh_effective_tenant()
