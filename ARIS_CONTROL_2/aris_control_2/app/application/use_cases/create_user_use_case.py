from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.domain.policies.tenant_context_policy import TenantContextPolicy
from aris_control_2.app.infrastructure.idempotency.key_factory import IdempotencyKeyFactory
from aris_control_2.app.infrastructure.sdk_adapter.admin_adapter import AdminAdapter
from aris_control_2.clients.aris3_client_sdk.http_client import APIError


class CreateUserUseCase:
    def __init__(self, adapter: AdminAdapter, state: SessionState) -> None:
        self.adapter = adapter
        self.state = state

    def execute(self, email: str, password: str, store_id: str | None = None) -> dict:
        if not self.state.context.can("users.create"):
            raise APIError(code="PERMISSION_DENIED", message="Missing users.create")
        allowed, reason = TenantContextPolicy.can_access_tenant_scoped_resources(self.state.context)
        if not allowed:
            raise APIError(code=reason, message=reason)
        try:
            result = self.adapter.create_user(
                tenant_id=self.state.context.effective_tenant_id,
                email=email,
                password=password,
                store_id=store_id,
                idempotency_key=IdempotencyKeyFactory.new_key("user-create"),
            )
        except APIError as error:
            if error.code in {"IDEMPOTENT_REPLAY", "IDEMPOTENCY_REPLAY"}:
                return {"status": "already_processed"}
            raise
        return result
