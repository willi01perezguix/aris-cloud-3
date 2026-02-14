from dataclasses import dataclass

from aris_control_2.app.application.state.session_state import SessionState
from aris_control_2.app.application.use_cases.load_me_use_case import LoadMeUseCase
from aris_control_2.app.application.use_cases.login_use_case import LoginUseCase
from aris_control_2.app.infrastructure.sdk_adapter.auth_adapter import AuthAdapter
from aris_control_2.clients.aris3_client_sdk.auth_store import AuthStore
from aris_control_2.clients.aris3_client_sdk.http_client import HttpClient


@dataclass
class FakeResponse:
    status_code: int
    payload: dict
    headers: dict | None = None

    def json(self):
        return self.payload

    @property
    def text(self):
        return str(self.payload)


def fake_transport(method, url, **kwargs):
    if url.endswith("/aris3/auth/login"):
        return FakeResponse(200, {"access_token": "token-1", "role": "SUPERADMIN", "tenant_id": None}, headers={})
    if url.endswith("/aris3/me"):
        return FakeResponse(
            200,
            {
                "role": "ADMIN",
                "tenant_id": "tenant-from-token",
                "permissions": ["stores.read", "users.actions.write"],
                "must_change_password": False,
            },
            headers={},
        )
    raise AssertionError(f"Unexpected call: {method} {url}")


def test_login_me_and_session_context() -> None:
    http = HttpClient(base_url="http://fake", transport=fake_transport)
    auth_store = AuthStore()
    state = SessionState()
    auth_adapter = AuthAdapter(http=http, auth_store=auth_store)

    LoginUseCase(auth_adapter=auth_adapter, state=state).execute("admin@example.com", "secret")
    LoadMeUseCase(auth_adapter=auth_adapter, state=state).execute()

    assert state.context.actor_role == "ADMIN"
    assert state.context.token_tenant_id == "tenant-from-token"
    assert state.context.effective_tenant_id == "tenant-from-token"
    assert state.context.effective_permissions == ["stores.read", "users.actions.write"]
    assert state.context.must_change_password is False
