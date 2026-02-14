from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.domain.policies.tenant_context_policy import TenantContextPolicy
from aris_control_2.app.infrastructure.idempotency.key_factory import IdempotencyKeyFactory
from aris_control_2.app.infrastructure.sdk_adapter.admin_adapter import AdminAdapter
from aris_control_2.clients.aris3_client_sdk.http_client import APIError


class UserActionsUseCase:
    def __init__(self, adapter: AdminAdapter, state: SessionState) -> None:
        self.adapter = adapter
        self.state = state

    def execute(self, user_id: str, action: str, payload: dict | None = None) -> dict:
        if not self.state.context.can("users.actions"):
            raise APIError(code="PERMISSION_DENIED", message="Missing users.actions")
        allowed, reason = TenantContextPolicy.can_access_tenant_scoped_resources(self.state.context)
        if not allowed:
            raise APIError(code=reason, message=reason)
        try:
            return self.adapter.user_action(
                user_id=user_id,
                action=action,
                payload=payload or {},
                idempotency_key=IdempotencyKeyFactory.new_key(f"user-action-{action}"),
            )
        except APIError as error:
            if error.code == "IDEMPOTENCY_REPLAY":
                return {"status": "already_processed"}
            raise
