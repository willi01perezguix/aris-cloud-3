from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.application.use_cases.create_store_use_case import CreateStoreUseCase
from aris_control_2.app.application.use_cases.list_stores_use_case import ListStoresUseCase


class FakeAdminAdapter:
    def __init__(self) -> None:
        self.calls = []

    def list_stores(self, tenant_id: str):
        self.calls.append(("list_stores", tenant_id))
        return [{"id": "s1", "tenant_id": tenant_id, "name": "Main"}]

    def create_store(self, tenant_id: str, name: str, idempotency_key: str):
        self.calls.append(("create_store", tenant_id, name, idempotency_key))
        return {"id": "s2", "tenant_id": tenant_id, "name": name}


def test_stores_use_effective_tenant_and_idempotency() -> None:
    adapter = FakeAdminAdapter()
    state = SessionState()
    state.context.actor_role = "ADMIN"
    state.context.token_tenant_id = "tenant-a"
    state.context.selected_tenant_id = "tenant-b"
    state.context.refresh_effective_tenant()

    ListStoresUseCase(adapter=adapter, state=state).execute()
    CreateStoreUseCase(adapter=adapter, state=state).execute("Branch")

    assert adapter.calls[0] == ("list_stores", "tenant-a")
    assert adapter.calls[1][0:3] == ("create_store", "tenant-a", "Branch")
    assert adapter.calls[1][3].startswith("store-")
