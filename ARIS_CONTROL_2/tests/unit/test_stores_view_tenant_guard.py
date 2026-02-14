from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.ui.views.stores_view import StoresView


class NoopUseCase:
    def execute(self, *args, **kwargs):
        return []


def test_stores_view_requires_selected_tenant(capsys) -> None:
    state = SessionState()
    state.context.effective_permissions = ["stores.view", "stores.create"]
    state.context.actor_role = "SUPERADMIN"

    view = StoresView(list_use_case=NoopUseCase(), create_use_case=NoopUseCase(), state=state)

    view.render()

    output = capsys.readouterr().out
    assert "Debes seleccionar tenant" in output
