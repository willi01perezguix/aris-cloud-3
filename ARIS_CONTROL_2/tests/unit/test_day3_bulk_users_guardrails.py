from dataclasses import dataclass

from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.ui.views.users_view import (
    UsersView,
    summarize_bulk_results,
    validate_homogeneous_tenant_selection,
)


@dataclass
class UserStub:
    id: str
    tenant_id: str
    email: str


class StaticUsersUseCase:
    def __init__(self, users):
        self._users = users

    def execute(self, *args, **kwargs):
        return self._users


class NoopUseCase:
    def execute(self, *args, **kwargs):
        return []


def test_validate_selection_requires_same_tenant() -> None:
    users = [
        UserStub(id="u-1", tenant_id="tenant-a", email="a@demo.com"),
        UserStub(id="u-2", tenant_id="tenant-b", email="b@demo.com"),
    ]

    allowed, reason = validate_homogeneous_tenant_selection(
        selected_ids=["u-1", "u-2"],
        users=users,
        tenant_id="tenant-a",
    )

    assert allowed is False
    assert "otro tenant" in reason


def test_bulk_action_blocked_without_users_actions_permission(monkeypatch, capsys) -> None:
    state = SessionState()
    state.context.selected_tenant_id = "tenant-a"
    state.context.effective_tenant_id = "tenant-a"
    state.context.actor_role = "ADMIN"
    state.context.token_tenant_id = "tenant-a"
    state.context.effective_permissions = ["users.view"]
    state.selected_user_rows = ["u-1"]
    state.selected_user_rows_tenant_id = "tenant-a"

    view = UsersView(
        list_use_case=StaticUsersUseCase([UserStub(id="u-1", tenant_id="tenant-a", email="a@demo.com")]),
        create_use_case=NoopUseCase(),
        actions_use_case=NoopUseCase(),
        list_stores_use_case=NoopUseCase(),
        state=state,
    )

    monkeypatch.setattr("builtins.input", lambda _: "b")

    view.render()

    output = capsys.readouterr().out
    assert "Acciones de usuario" in output
    assert "No tienes permiso" in output


def test_bulk_results_aggregation_counts_success_and_error() -> None:
    summary = summarize_bulk_results(
        [
            {"user_id": "u-1", "result": "success"},
            {"user_id": "u-2", "result": "error", "code": "VALIDATION_ERROR"},
            {"user_id": "u-3", "result": "success"},
        ]
    )

    assert summary == {"total": 3, "success": 2, "failed": 1}
