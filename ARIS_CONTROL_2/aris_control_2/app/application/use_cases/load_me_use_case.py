from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.infrastructure.sdk_adapter.auth_adapter import AuthAdapter


class LoadMeUseCase:
    def __init__(self, auth_adapter: AuthAdapter, state: SessionState) -> None:
        self.auth_adapter = auth_adapter
        self.state = state

    def execute(self) -> None:
        me = self.auth_adapter.me()
        self.state.context.effective_permissions = me.get("permissions", [])
