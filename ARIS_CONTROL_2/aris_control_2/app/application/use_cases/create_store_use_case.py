import inspect

from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.domain.policies.tenant_context_policy import TenantContextPolicy
from aris_control_2.app.infrastructure.idempotency.key_factory import IdempotencyKeyFactory
from aris_control_2.app.infrastructure.sdk_adapter.admin_adapter import AdminAdapter
from aris_control_2.clients.aris3_client_sdk.http_client import APIError
from aris_control_2.clients.aris3_client_sdk.tracing import new_trace_id


class CreateStoreUseCase:
    def __init__(self, adapter: AdminAdapter, state: SessionState) -> None:
        self.adapter = adapter
        self.state = state

    def execute(self, name: str, idempotency_key: str | None = None, transaction_id: str | None = None) -> dict:
        if not self.state.context.can("stores.create"):
            raise APIError(code="PERMISSION_DENIED", message="Missing stores.create")
        tenant_id, reason = TenantContextPolicy.resolve_mutation_tenant_id(self.state.context)
        if not tenant_id:
            raise APIError(code=reason, message=reason)
        try:
            payload = {
                "tenant_id": tenant_id,
                "name": name,
                "idempotency_key": idempotency_key or IdempotencyKeyFactory.new_key("store-create"),
            }
            if "transaction_id" in inspect.signature(self.adapter.create_store).parameters:
                payload["transaction_id"] = transaction_id or new_trace_id()
            result = self.adapter.create_store(**payload)
        except APIError as error:
            if error.code in {"IDEMPOTENT_REPLAY", "IDEMPOTENCY_REPLAY"}:
                return {"status": "already_processed"}
            raise
        return result
