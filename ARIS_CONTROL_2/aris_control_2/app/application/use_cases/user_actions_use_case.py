from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.infrastructure.idempotency.key_factory import IdempotencyKeyFactory
from aris_control_2.app.infrastructure.sdk_adapter.admin_adapter import AdminAdapter


class UserActionsUseCase:
    def __init__(self, adapter: AdminAdapter, state: SessionState) -> None:
        self.adapter = adapter
        self.state = state

    def execute(self, user_id: str, action: str, payload: dict | None = None) -> dict:
        result = self.adapter.user_action(
            user_id=user_id,
            action=action,
            payload=payload or {},
            idempotency_key=IdempotencyKeyFactory.new_key(f"user-{action}"),
        )
        self.state.users_cache = self.adapter.list_users(self.state.context.effective_tenant_id)
        return result
