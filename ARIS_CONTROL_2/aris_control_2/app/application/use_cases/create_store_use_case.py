from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.domain.policies.tenant_context_policy import TenantContextPolicy
from aris_control_2.app.infrastructure.idempotency.key_factory import IdempotencyKeyFactory
from aris_control_2.app.infrastructure.sdk_adapter.admin_adapter import AdminAdapter
from aris_control_2.clients.aris3_client_sdk.http_client import APIError


class CreateStoreUseCase:
    def __init__(self, adapter: AdminAdapter, state: SessionState) -> None:
        self.adapter = adapter
        self.state = state

    def execute(self, name: str) -> dict:
        if not self.state.context.can("stores.create"):
            raise APIError(code="PERMISSION_DENIED", message="Missing stores.create")
        allowed, reason = TenantContextPolicy.can_access_tenant_scoped_resources(self.state.context)
        if not allowed:
            raise APIError(code=reason, message=reason)
        try:
            result = self.adapter.create_store(
                tenant_id=self.state.context.effective_tenant_id,
                name=name,
                idempotency_key=IdempotencyKeyFactory.new_key("store-create"),
            )
        except APIError as error:
            if error.code in {"IDEMPOTENT_REPLAY", "IDEMPOTENCY_REPLAY"}:
                return {"status": "already_processed"}
            raise
        return result
