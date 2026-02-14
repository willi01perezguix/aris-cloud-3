from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.domain.policies.tenant_context_policy import TenantContextPolicy
from aris_control_2.app.infrastructure.sdk_adapter.admin_adapter import AdminAdapter


class ListUsersUseCase:
    def __init__(self, adapter: AdminAdapter, state: SessionState) -> None:
        self.adapter = adapter
        self.state = state

    def execute(self) -> list:
        allowed, reason = TenantContextPolicy.can_access_tenant_scoped_resources(self.state.context)
        if not allowed:
            raise ValueError(reason)
        users = self.adapter.list_users(self.state.context.effective_tenant_id)
        self.state.users_cache = users
        return users
