from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.application.use_cases.create_user_use_case import CreateUserUseCase
from aris_control_2.app.application.use_cases.list_stores_use_case import ListStoresUseCase
from aris_control_2.app.application.use_cases.list_users_use_case import ListUsersUseCase
from aris_control_2.app.application.use_cases.user_actions_use_case import UserActionsUseCase


class FakeAdminAdapter:
    def __init__(self) -> None:
        self.calls = []

    def list_stores(self, tenant_id: str):
        self.calls.append(("list_stores", tenant_id))
        return [{"id": "store-a", "tenant_id": tenant_id, "name": "Main"}]

    def list_users(self, tenant_id: str):
        self.calls.append(("list_users", tenant_id))
        return [{"id": "user-a", "tenant_id": tenant_id, "email": "a@b.com"}]

    def create_user(self, tenant_id: str, email: str, password: str, store_id: str | None, idempotency_key: str):
        self.calls.append(("create_user", tenant_id, email, store_id, idempotency_key))
        return {"id": "user-new", "tenant_id": tenant_id, "email": email}

    def user_action(self, user_id: str, action: str, payload: dict, idempotency_key: str):
        self.calls.append(("user_action", user_id, action, payload, idempotency_key))
        return {"ok": True}


def test_users_use_effective_tenant_and_actions_refresh() -> None:
    adapter = FakeAdminAdapter()
    state = SessionState()
    state.context.actor_role = "ADMIN"
    state.context.token_tenant_id = "tenant-token"
    state.context.selected_tenant_id = "tenant-ui"
    state.context.effective_permissions = ["users.view", "stores.view", "users.create", "users.actions"]
    state.context.refresh_effective_tenant()

    ListUsersUseCase(adapter=adapter, state=state).execute()
    ListStoresUseCase(adapter=adapter, state=state).execute()
    CreateUserUseCase(adapter=adapter, state=state).execute("x@y.com", "secret", store_id="store-a")
    UserActionsUseCase(adapter=adapter, state=state).execute("user-a", "set_status", {"status": "INACTIVE"})

    assert adapter.calls[0] == ("list_users", "tenant-token")
    assert adapter.calls[1] == ("list_stores", "tenant-token")
    assert adapter.calls[2][0:4] == ("create_user", "tenant-token", "x@y.com", "store-a")
    assert adapter.calls[2][4].startswith("aris2-user-create-")
    assert adapter.calls[3][0:3] == ("user_action", "user-a", "set_status")
    assert adapter.calls[3][4].startswith("aris2-user-action-set-status-")
