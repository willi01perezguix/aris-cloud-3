from dataclasses import dataclass

from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.ui.views.users_view import (
    UsersView,
    render_last_admin_action,
    should_enable_sensitive_confirm,
    validate_sensitive_confirmation_inputs,
    validate_store_for_selected_tenant,
    validate_user_action_context,
)


@dataclass
class StoreStub:
    id: str
    tenant_id: str
    name: str


class NoopUseCase:
    def execute(self, *args, **kwargs):
        return []


def test_validate_store_blocks_unknown_store() -> None:
    stores = [StoreStub(id="s-1", tenant_id="t-1", name="Main")]

    allowed, reason = validate_store_for_selected_tenant("t-1", "missing-store", stores)

    assert allowed is False
    assert "no existe" in reason


def test_validate_store_blocks_tenant_store_mismatch() -> None:
    stores = [StoreStub(id="s-1", tenant_id="tenant-b", name="Other")]

    allowed, reason = validate_store_for_selected_tenant("tenant-a", "s-1", stores)

    assert allowed is False
    assert "Mismatch tenant↔store" in reason


def test_validate_store_accepts_match() -> None:
    stores = [StoreStub(id="s-1", tenant_id="tenant-a", name="Main")]

    allowed, reason = validate_store_for_selected_tenant("tenant-a", "s-1", stores)

    assert allowed is True
    assert reason == ""


def test_users_view_requires_selected_tenant(capsys) -> None:
    state = SessionState()
    state.context.effective_permissions = ["users.view", "users.create", "users.actions"]
    state.context.actor_role = "SUPERADMIN"

    view = UsersView(
        list_use_case=NoopUseCase(),
        create_use_case=NoopUseCase(),
        actions_use_case=NoopUseCase(),
        list_stores_use_case=NoopUseCase(),
        state=state,
    )

    view.render()

    output = capsys.readouterr().out
    assert "Debes seleccionar tenant" in output


def test_validate_user_action_context_blocks_when_tenant_is_missing() -> None:
    allowed, reason = validate_user_action_context(
        selected_tenant_id=None,
        effective_tenant_id=None,
        action_gate_allowed=True,
        action_gate_reason="",
        user_id="user-1",
        action="set_status",
        payload={"status": "ACTIVE"},
        users=[type("UserStub", (), {"id": "user-1", "tenant_id": "tenant-a"})()],
    )

    assert allowed is False
    assert "seleccionar tenant" in reason


def test_validate_user_action_context_blocks_tenant_mismatch() -> None:
    allowed, reason = validate_user_action_context(
        selected_tenant_id="tenant-a",
        effective_tenant_id="tenant-a",
        action_gate_allowed=True,
        action_gate_reason="",
        user_id="user-1",
        action="set_role",
        payload={"role": "MANAGER"},
        users=[type("UserStub", (), {"id": "user-1", "tenant_id": "tenant-b"})()],
    )

    assert allowed is False
    assert "mismatch tenant" in reason


def test_validate_user_action_context_blocks_missing_permission() -> None:
    allowed, reason = validate_user_action_context(
        selected_tenant_id="tenant-a",
        effective_tenant_id="tenant-a",
        action_gate_allowed=False,
        action_gate_reason="No tienes permiso para esta acción (users.actions).",
        user_id="user-1",
        action="reset_password",
        payload={"new_password": "secret"},
        users=[type("UserStub", (), {"id": "user-1", "tenant_id": "tenant-a"})()],
    )

    assert allowed is False
    assert "No tienes permiso" in reason


def test_validate_user_action_context_accepts_valid_action() -> None:
    allowed, reason = validate_user_action_context(
        selected_tenant_id="tenant-a",
        effective_tenant_id="tenant-a",
        action_gate_allowed=True,
        action_gate_reason="",
        user_id="user-1",
        action="set_status",
        payload={"status": "INACTIVE"},
        users=[type("UserStub", (), {"id": "user-1", "tenant_id": "tenant-a"})()],
    )

    assert allowed is True
    assert reason == ""


def test_render_last_admin_action_shows_trace(capsys) -> None:
    state = SessionState()
    state.last_admin_action = {
        "action": "user.set_role",
        "timestamp_local": "2026-01-01T00:00:00",
        "result": "OK",
        "trace_id": "trace-123",
    }

    render_last_admin_action(state)

    output = capsys.readouterr().out
    assert "última acción" in output
    assert "trace-123" in output


def test_validate_sensitive_confirmation_inputs_requires_checkbox() -> None:
    allowed, reason = validate_sensitive_confirmation_inputs(False, "CONFIRM-SET_ROLE", "CONFIRM-SET_ROLE")

    assert allowed is False
    assert "confirmación explícita" in reason


def test_validate_sensitive_confirmation_inputs_requires_exact_text() -> None:
    allowed, reason = validate_sensitive_confirmation_inputs(True, "confirm-set-role", "CONFIRM-SET_ROLE")

    assert allowed is False
    assert "exactamente" in reason


def test_should_enable_sensitive_confirm_blocks_invalid_prevalidation() -> None:
    enabled, reason = should_enable_sensitive_confirm(
        valid_action=False,
        confirmation_checked=True,
        confirmation_text="CONFIRM-SET_STATUS",
        expected_text="CONFIRM-SET_STATUS",
    )

    assert enabled is False
    assert "validaciones previas" in reason


def test_should_enable_sensitive_confirm_accepts_valid_inputs() -> None:
    enabled, reason = should_enable_sensitive_confirm(
        valid_action=True,
        confirmation_checked=True,
        confirmation_text="CONFIRM-RESET_PASSWORD",
        expected_text="CONFIRM-RESET_PASSWORD",
    )

    assert enabled is True
    assert reason == ""
