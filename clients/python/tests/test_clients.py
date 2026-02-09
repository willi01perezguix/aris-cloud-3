from __future__ import annotations

import responses

from aris3_client_sdk import load_config
from aris3_client_sdk.clients.access_control import AccessControlClient
from aris3_client_sdk.clients.auth import AuthClient
from aris3_client_sdk.exceptions import ForbiddenError, UnauthorizedError
from aris3_client_sdk.http_client import HttpClient
from aris3_client_sdk.tracing import TraceContext


def _client(base_url: str) -> HttpClient:
    cfg = load_config()
    object.__setattr__(cfg, "api_base_url", base_url)
    return HttpClient(cfg, trace=TraceContext())


@responses.activate
def test_login_me_flow(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    responses.add(
        responses.POST,
        "https://api.example.com/aris3/auth/login",
        json={"access_token": "token", "must_change_password": False, "trace_id": "trace"},
        status=200,
    )
    responses.add(
        responses.GET,
        "https://api.example.com/aris3/me",
        json={
            "id": "user-1",
            "username": "demo",
            "email": "demo@example.com",
            "tenant_id": "tenant",
            "store_id": "store",
            "role": "ADMIN",
            "status": "ACTIVE",
            "is_active": True,
            "must_change_password": False,
            "trace_id": "trace",
        },
        status=200,
    )

    auth = AuthClient(http=http)
    token = auth.login("demo", "pass")
    authed = AuthClient(http=http, access_token=token.access_token)
    user = authed.me()

    assert user.username == "demo"


@responses.activate
def test_effective_permissions_fetch(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    responses.add(
        responses.GET,
        "https://api.example.com/aris3/access-control/effective-permissions",
        json={
            "user_id": "user-1",
            "tenant_id": "tenant",
            "store_id": "store",
            "role": "ADMIN",
            "permissions": [{"key": "stock.view", "allowed": True, "source": "template"}],
            "subject": {
                "user_id": "user-1",
                "tenant_id": "tenant",
                "store_id": "store",
                "role": "ADMIN",
            },
            "denies_applied": [],
            "sources_trace": {
                "template": {"allow": ["stock.view"], "deny": []},
                "tenant": {"allow": [], "deny": []},
                "store": {"allow": [], "deny": []},
                "user": {"allow": [], "deny": []},
            },
            "trace_id": "trace",
        },
        status=200,
    )

    client = AccessControlClient(http=http, access_token="token")
    response = client.effective_permissions()
    assert response.permissions[0].key == "stock.view"


@responses.activate
def test_unauthorized_forbidden(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    responses.add(
        responses.GET,
        "https://api.example.com/aris3/me",
        json={"code": "INVALID_TOKEN", "message": "no", "details": None, "trace_id": "trace"},
        status=401,
    )
    responses.add(
        responses.GET,
        "https://api.example.com/aris3/access-control/effective-permissions",
        json={"code": "PERMISSION_DENIED", "message": "no", "details": None, "trace_id": "trace"},
        status=403,
    )

    auth = AuthClient(http=http, access_token="bad")
    try:
        auth.me()
    except UnauthorizedError:
        pass
    else:
        raise AssertionError("Expected UnauthorizedError")

    access = AccessControlClient(http=http, access_token="bad")
    try:
        access.effective_permissions()
    except ForbiddenError:
        pass
    else:
        raise AssertionError("Expected ForbiddenError")
