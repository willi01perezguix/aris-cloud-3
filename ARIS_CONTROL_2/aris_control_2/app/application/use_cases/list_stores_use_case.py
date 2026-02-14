from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.domain.policies.tenant_context_policy import TenantContextPolicy
from aris_control_2.app.infrastructure.sdk_adapter.admin_adapter import AdminAdapter


class ListStoresUseCase:
    def __init__(self, adapter: AdminAdapter, state: SessionState) -> None:
        self.adapter = adapter
        self.state = state

    def execute(self) -> list:
        allowed, reason = TenantContextPolicy.can_access_tenant_scoped_resources(self.state.context)
        if not allowed:
            raise ValueError(reason)
        stores = self.adapter.list_stores(self.state.context.effective_tenant_id)
        self.state.stores_cache = stores
        return stores
