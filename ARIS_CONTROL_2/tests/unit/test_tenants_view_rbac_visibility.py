from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.ui.views.tenants_view import TenantsView


class TenantStub:
    def __init__(self, tenant_id: str, name: str) -> None:
        self.id = tenant_id
        self.name = name


class AdapterStub:
    def list_tenants(self):
        return [TenantStub("t-1", "Tenant 1")]


def test_tenants_view_shows_disabled_actions_when_permission_missing(capsys) -> None:
    state = SessionState()
    state.context.actor_role = "MANAGER"
    state.context.effective_permissions = ["tenants.view"]

    view = TenantsView(adapter=AdapterStub(), state=state)

    view.render()

    output = capsys.readouterr().out
    assert "No tienes permiso para esta acción" in output
    assert "Crear Tenant" in output
    assert "Editar Tenant" in output
    assert "Suspender Tenant" in output
