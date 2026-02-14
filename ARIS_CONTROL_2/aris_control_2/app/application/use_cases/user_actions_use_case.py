import inspect

from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.domain.policies.tenant_context_policy import TenantContextPolicy
from aris_control_2.app.infrastructure.idempotency.key_factory import IdempotencyKeyFactory
from aris_control_2.app.infrastructure.sdk_adapter.admin_adapter import AdminAdapter
from aris_control_2.clients.aris3_client_sdk.http_client import APIError
from aris_control_2.clients.aris3_client_sdk.tracing import new_trace_id


class UserActionsUseCase:
    def __init__(self, adapter: AdminAdapter, state: SessionState) -> None:
        self.adapter = adapter
        self.state = state

    def execute(
        self,
        user_id: str,
        action: str,
        payload: dict | None = None,
        *,
        idempotency_key: str | None = None,
        transaction_id: str | None = None,
    ) -> dict:
        if not self.state.context.can("users.actions"):
            raise APIError(code="PERMISSION_DENIED", message="Missing users.actions")
        allowed, reason = TenantContextPolicy.can_access_tenant_scoped_resources(self.state.context)
        if not allowed:
            raise APIError(code=reason, message=reason)
        try:
            request = {
                "user_id": user_id,
                "action": action,
                "payload": payload or {},
                "idempotency_key": idempotency_key or IdempotencyKeyFactory.new_key(f"user-action-{action}"),
            }
            if "transaction_id" in inspect.signature(self.adapter.user_action).parameters:
                request["transaction_id"] = transaction_id or new_trace_id()
            return self.adapter.user_action(**request)
        except APIError as error:
            if error.code in {"IDEMPOTENT_REPLAY", "IDEMPOTENCY_REPLAY"}:
                return {"status": "already_processed"}
            raise
