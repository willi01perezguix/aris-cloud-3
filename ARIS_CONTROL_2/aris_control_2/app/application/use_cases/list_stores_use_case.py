from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.domain.policies.tenant_context_policy import TenantContextPolicy
from aris_control_2.app.infrastructure.sdk_adapter.admin_adapter import AdminAdapter
from aris_control_2.clients.aris3_client_sdk.http_client import APIError


class ListStoresUseCase:
    def __init__(self, adapter: AdminAdapter, state: SessionState) -> None:
        self.adapter = adapter
        self.state = state

    def execute(self) -> list:
        if not self.state.context.can("stores.view"):
            raise APIError(code="PERMISSION_DENIED", message="Missing stores.view")

        allowed, reason = TenantContextPolicy.can_access_tenant_scoped_resources(self.state.context)
        if not allowed:
            raise APIError(code=reason, message=reason)

        tenant_id = TenantContextPolicy.resolve_effective_tenant_id(self.state.context)
        if not tenant_id:
            raise APIError(code="TENANT_SCOPE_REQUIRED", message="TENANT_SCOPE_REQUIRED")

        stores = self.adapter.list_stores(tenant_id)
        self.state.stores_cache = stores
        return stores
