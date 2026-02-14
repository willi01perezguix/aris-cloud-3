from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.infrastructure.sdk_adapter.admin_adapter import AdminAdapter


class TenantsView:
    def __init__(self, adapter: AdminAdapter, state: SessionState) -> None:
        self.adapter = adapter
        self.state = state

    def render(self) -> None:
        tenants = self.adapter.list_tenants()
        print("-- Tenants --")
        for tenant in tenants:
            selected = "*" if tenant.id == self.state.context.selected_tenant_id else " "
            print(f"{selected} {tenant.id} :: {tenant.name}")
