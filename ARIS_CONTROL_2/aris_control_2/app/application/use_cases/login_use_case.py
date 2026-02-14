from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.infrastructure.sdk_adapter.auth_adapter import AuthAdapter


class LoginUseCase:
    def __init__(self, auth_adapter: AuthAdapter, state: SessionState) -> None:
        self.auth_adapter = auth_adapter
        self.state = state

    def execute(self, username_or_email: str, password: str) -> None:
        result = self.auth_adapter.login(username_or_email=username_or_email, password=password)
        self.state.context.actor_role = result.get("role")
        self.state.context.token_tenant_id = result.get("tenant_id")
