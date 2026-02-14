import inspect

from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.domain.policies.tenant_context_policy import TenantContextPolicy
from aris_control_2.app.infrastructure.idempotency.key_factory import IdempotencyKeyFactory
from aris_control_2.app.infrastructure.sdk_adapter.admin_adapter import AdminAdapter
from aris_control_2.clients.aris3_client_sdk.http_client import APIError
from aris_control_2.clients.aris3_client_sdk.tracing import new_trace_id


class CreateUserUseCase:
    def __init__(self, adapter: AdminAdapter, state: SessionState) -> None:
        self.adapter = adapter
        self.state = state

    def execute(
        self,
        email: str,
        password: str,
        idempotency_key: str | None = None,
        transaction_id: str | None = None,
        store_id: str | None = None,
    ) -> dict:
        if not self.state.context.can("users.create"):
            raise APIError(code="PERMISSION_DENIED", message="Missing users.create")
        tenant_id, reason = TenantContextPolicy.resolve_mutation_tenant_id(self.state.context)
        if not tenant_id:
            raise APIError(code=reason, message=reason)
        try:
            payload = {
                "tenant_id": tenant_id,
                "email": email,
                "password": password,
                "store_id": store_id,
                "idempotency_key": idempotency_key or IdempotencyKeyFactory.new_key("user-create"),
            }
            if "transaction_id" in inspect.signature(self.adapter.create_user).parameters:
                payload["transaction_id"] = transaction_id or new_trace_id()
            result = self.adapter.create_user(**payload)
        except APIError as error:
            if error.code in {"IDEMPOTENT_REPLAY", "IDEMPOTENCY_REPLAY"}:
                return {"status": "already_processed"}
            raise
        return result
