from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.application.use_cases.create_store_use_case import CreateStoreUseCase
from aris_control_2.app.application.use_cases.create_user_use_case import CreateUserUseCase
from aris_control_2.app.application.use_cases.user_actions_use_case import UserActionsUseCase
from aris_control_2.app.infrastructure.errors.error_mapper import ErrorMapper
from aris_control_2.clients.aris3_client_sdk.http_client import APIError


class GuardrailAdapter:
    def __init__(self) -> None:
        self.calls = []

    def create_store(self, tenant_id: str, name: str, idempotency_key: str):
        self.calls.append(("create_store", tenant_id, name, idempotency_key))
        return {"id": "store-1", "tenant_id": tenant_id, "name": name}

    def create_user(self, tenant_id: str, email: str, password: str, store_id: str | None, idempotency_key: str):
        self.calls.append(("create_user", tenant_id, email, store_id, idempotency_key))
        if store_id == "store-cross":
            raise APIError(
                code="TENANT_STORE_MISMATCH",
                message="Store outside effective tenant",
                trace_id="trace-u4-1",
                status_code=400,
            )
        if email == "replay@example.com":
            raise APIError(code="IDEMPOTENT_REPLAY", message="Already processed", trace_id="trace-u6-create")
        return {"id": "user-1", "tenant_id": tenant_id, "email": email}

    def user_action(self, user_id: str, action: str, payload: dict, idempotency_key: str):
        self.calls.append(("user_action", user_id, action, payload, idempotency_key))
        if action == "reset_password":
            raise APIError(code="PERMISSION_DENIED", message="not allowed", trace_id="trace-u5-1", status_code=403)
        if action == "set_role":
            raise APIError(code="IDEMPOTENT_REPLAY", message="Already processed", trace_id="trace-u6-action")
        return {"ok": True}


def test_u1_superadmin_without_selected_tenant_blocked_from_stores_users() -> None:
    state = SessionState()
    state.context.actor_role = "SUPERADMIN"
    state.context.effective_permissions = ["stores.create", "users.create"]
    state.context.refresh_effective_tenant()
    adapter = GuardrailAdapter()

    for use_case, args in [
        (CreateStoreUseCase(adapter=adapter, state=state), ("Main",)),
        (CreateUserUseCase(adapter=adapter, state=state), ("a@b.com", "secret", None)),
    ]:
        try:
            use_case.execute(*args)
            raised = False
        except APIError as error:
            raised = True
            assert error.code == "TENANT_CONTEXT_REQUIRED"

        assert raised


def test_u4_cross_tenant_store_in_user_create_surfaces_trace_id() -> None:
    state = SessionState()
    state.context.actor_role = "ADMIN"
    state.context.token_tenant_id = "tenant-a"
    state.context.effective_permissions = ["users.create"]
    state.context.refresh_effective_tenant()
    adapter = GuardrailAdapter()

    try:
        CreateUserUseCase(adapter=adapter, state=state).execute("x@y.com", "secret", store_id="store-cross")
        raised = False
    except APIError as error:
        raised = True
        payload = ErrorMapper.to_payload(error)
        assert payload["code"] == "TENANT_STORE_MISMATCH"
        assert payload["trace_id"] == "trace-u4-1"

    assert raised


def test_u5_permission_denied_action_visible_with_trace_id() -> None:
    state = SessionState()
    state.context.actor_role = "ADMIN"
    state.context.token_tenant_id = "tenant-a"
    state.context.effective_permissions = ["users.actions"]
    state.context.refresh_effective_tenant()
    adapter = GuardrailAdapter()

    try:
        UserActionsUseCase(adapter=adapter, state=state).execute("user-1", "reset_password", {"new_password": "x"})
        raised = False
    except APIError as error:
        raised = True
        display = ErrorMapper.to_display_message(error)
        assert "PERMISSION_DENIED" in display
        assert "trace-u5-1" in display

    assert raised


def test_u6_idempotent_replay_does_not_duplicate_create_or_action() -> None:
    state = SessionState()
    state.context.actor_role = "ADMIN"
    state.context.token_tenant_id = "tenant-a"
    state.context.effective_permissions = ["users.create", "users.actions"]
    state.context.refresh_effective_tenant()
    adapter = GuardrailAdapter()

    create_result = CreateUserUseCase(adapter=adapter, state=state).execute("replay@example.com", "secret")
    action_result = UserActionsUseCase(adapter=adapter, state=state).execute("user-1", "set_role", {"role": "MANAGER"})

    assert create_result == {"status": "already_processed"}
    assert action_result == {"status": "already_processed"}
    assert len([call for call in adapter.calls if call[0] == "create_user"]) == 1
    assert len([call for call in adapter.calls if call[0] == "user_action"]) == 1
