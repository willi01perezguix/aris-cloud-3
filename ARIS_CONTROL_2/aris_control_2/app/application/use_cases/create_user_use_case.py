from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.domain.policies.tenant_context_policy import TenantContextPolicy
from aris_control_2.app.infrastructure.idempotency.key_factory import IdempotencyKeyFactory
from aris_control_2.app.infrastructure.sdk_adapter.admin_adapter import AdminAdapter


class CreateUserUseCase:
    def __init__(self, adapter: AdminAdapter, state: SessionState) -> None:
        self.adapter = adapter
        self.state = state

    def execute(self, email: str, password: str, store_id: str | None = None) -> dict:
        allowed, reason = TenantContextPolicy.can_access_tenant_scoped_resources(self.state.context)
        if not allowed:
            raise ValueError(reason)
        result = self.adapter.create_user(
            tenant_id=self.state.context.effective_tenant_id,
            email=email,
            password=password,
            store_id=store_id,
            idempotency_key=IdempotencyKeyFactory.new_key("user"),
        )
        self.state.users_cache = self.adapter.list_users(self.state.context.effective_tenant_id)
        return result
