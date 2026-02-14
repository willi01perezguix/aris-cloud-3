from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.infrastructure.errors.error_mapper import ErrorMapper
from aris_control_2.app.infrastructure.sdk_adapter.admin_adapter import AdminAdapter
from aris_control_2.app.ui.components.error_banner import ErrorBanner
from aris_control_2.app.ui.components.permission_gate import PermissionGate


class TenantsView:
    def __init__(self, adapter: AdminAdapter, state: SessionState) -> None:
        self.adapter = adapter
        self.state = state

    def render(self) -> None:
        gate = PermissionGate.check(self.state.context, "tenants.view")
        if not gate.allowed:
            ErrorBanner.show(gate.reason)
            return
        print("[loading] cargando tenants...")
        try:
            tenants = self.adapter.list_tenants()
            if not tenants:
                print("[empty] No hay tenants disponibles.")
                return
            print("[ready] -- Tenants --")
            for tenant in tenants:
                selected = "*" if tenant.id == self.state.context.selected_tenant_id else " "
                print(f"{selected} {tenant.id} :: {tenant.name}")
        except Exception as error:
            ErrorBanner.show(ErrorMapper.to_payload(error))
