from aris_control_2.app.application.state.session_state import SessionState


class SelectTenantUseCase:
    def __init__(self, state: SessionState) -> None:
        self.state = state

    def execute(self, tenant_id: str | None) -> None:
        self.state.context.selected_tenant_id = tenant_id
        self.state.context.refresh_effective_tenant()
        self.state.clear_tenant_scoped_data()
