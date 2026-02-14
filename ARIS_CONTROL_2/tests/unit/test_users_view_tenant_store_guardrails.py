from dataclasses import dataclass

from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.ui.views.users_view import UsersView, validate_store_for_selected_tenant


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
