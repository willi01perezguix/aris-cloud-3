from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.domain.policies.tenant_context_policy import TenantContextPolicy


class SelectTenantUseCase:
    def __init__(self, state: SessionState) -> None:
        self.state = state

    def execute(self, tenant_id: str | None) -> None:
        self.state.context.selected_tenant_id = tenant_id
        self.state.context.effective_tenant_id = TenantContextPolicy.resolve_effective_tenant_id(self.state.context)
