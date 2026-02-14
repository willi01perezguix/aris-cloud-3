from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.domain.policies.tenant_context_policy import TenantContextPolicy
from aris_control_2.app.infrastructure.sdk_adapter.admin_adapter import AdminAdapter
from aris_control_2.clients.aris3_client_sdk.http_client import APIError


class ListUsersUseCase:
    def __init__(self, adapter: AdminAdapter, state: SessionState) -> None:
        self.adapter = adapter
        self.state = state

    def execute(self) -> list:
        if not self.state.context.can("users.view"):
            raise APIError(code="PERMISSION_DENIED", message="Missing users.view")
        allowed, reason = TenantContextPolicy.can_access_tenant_scoped_resources(self.state.context)
        if not allowed:
            raise APIError(code=reason, message=reason)
        users = self.adapter.list_users(self.state.context.effective_tenant_id)
        self.state.users_cache = users
        return users
