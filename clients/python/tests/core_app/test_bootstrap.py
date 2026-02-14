from __future__ import annotations

from dataclasses import dataclass

import pytest

from aris3_client_sdk.models import (
    EffectivePermissionSubject,
    EffectivePermissionsResponse,
    EffectivePermissionsTrace,
    PermissionEntry,
    PermissionSourceTrace,
    TokenResponse,
    UserResponse,
)

from app.bootstrap import CoreAppBootstrap
from app.state import Route
from services.permissions_service import PermissionGate


@pytest.fixture(autouse=True)
def _set_api_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")


@dataclass
class FakeAuthClient:
    login_error: Exception | None = None
    profile: UserResponse | None = None

    def login(self, username_or_email: str, password: str) -> TokenResponse:
        if self.login_error:
            raise self.login_error
        return TokenResponse(access_token="token-123", must_change_password=False, trace_id="trace-login")

    def me(self) -> UserResponse:
        assert self.profile is not None
        return self.profile

    def change_password(self, current_password: str, new_password: str, idempotency_key: str) -> TokenResponse:
        return TokenResponse(access_token="token-456", must_change_password=False, trace_id="trace-change")


@dataclass
class FakeAccessControlClient:
    permissions: list[PermissionEntry]

    def effective_permissions(self) -> EffectivePermissionsResponse:
        return EffectivePermissionsResponse(
            user_id="user-1",
            tenant_id="tenant-1",
            store_id="store-1",
            role="CASHIER",
            permissions=self.permissions,
            subject=EffectivePermissionSubject(user_id="user-1", tenant_id="tenant-1", store_id="store-1"),
            denies_applied=[],
            sources_trace=EffectivePermissionsTrace(
                template=PermissionSourceTrace(),
                tenant=PermissionSourceTrace(),
                store=PermissionSourceTrace(),
                user=PermissionSourceTrace(),
            ),
            trace_id="trace-permissions",
        )


@dataclass
class FakeHealthClient:
    payload: dict[str, object] | None = None
    error: Exception | None = None

    def health(self) -> dict[str, object]:
        if self.error:
            raise self.error
        return self.payload or {"ok": True}


class FakeSession:
    def __init__(
        self,
        profile: UserResponse,
        permissions: list[PermissionEntry],
        token: str | None = None,
        health_payload: dict[str, object] | None = None,
        health_error: Exception | None = None,
    ) -> None:
        self.token = token
        self.user: UserResponse | None = None
        self._auth = FakeAuthClient(profile=profile)
        self._ac = FakeAccessControlClient(permissions=permissions)
        self._health = FakeHealthClient(payload=health_payload, error=health_error)

    def auth_client(self) -> FakeAuthClient:
        return self._auth

    def access_control_client(self) -> FakeAccessControlClient:
        return self._ac

    def health_client(self) -> FakeHealthClient:
        return self._health

    def establish(self, token: TokenResponse, user: UserResponse | None) -> None:
        self.token = token.access_token
        self.user = user

    def logout(self) -> None:
        self.token = None
        self.user = None


def _profile(must_change_password: bool = False) -> UserResponse:
    return UserResponse(
        id="user-1",
        username="alice",
        tenant_id="tenant-1",
        store_id="store-1",
        role="CASHIER",
        must_change_password=must_change_password,
        trace_id="trace-me",
    )


def test_login_success_path_loads_shell() -> None:
    session = FakeSession(
        profile=_profile(),
        permissions=[PermissionEntry(key="stock.view", allowed=True), PermissionEntry(key="reports.view", allowed=True)],
    )
    bootstrap = CoreAppBootstrap(session=session)  # type: ignore[arg-type]

    result = bootstrap.login("alice", "safe-password")

    assert result.route is Route.SHELL
    assert bootstrap.state.session.user is not None
    assert bootstrap.state.allowed_permissions == {"stock.view", "reports.view"}


def test_login_failure_shows_error_and_stays_on_login() -> None:
    session = FakeSession(profile=_profile(), permissions=[])
    session._auth.login_error = RuntimeError("invalid credentials")
    bootstrap = CoreAppBootstrap(session=session)  # type: ignore[arg-type]

    result = bootstrap.login("alice", "wrong")

    assert result.route is Route.LOGIN
    assert result.error_message is not None


def test_must_change_password_routing() -> None:
    session = FakeSession(profile=_profile(must_change_password=True), permissions=[])
    bootstrap = CoreAppBootstrap(session=session)  # type: ignore[arg-type]

    result = bootstrap.login("alice", "safe-password")

    assert result.route is Route.CHANGE_PASSWORD


def test_permission_gate_default_deny_and_deny_over_allow() -> None:
    gate = PermissionGate(
        [
            PermissionEntry(key="stock.view", allowed=True),
            PermissionEntry(key="stock.view", allowed=False),
            PermissionEntry(key="reports.view", allowed=True),
        ]
    )

    assert gate.is_allowed("stock.view") is False
    assert gate.is_allowed("reports.view") is True
    assert gate.is_allowed("unknown.permission") is False


def test_permissioned_menu_hides_unauthorized_modules() -> None:
    session = FakeSession(
        profile=_profile(),
        permissions=[PermissionEntry(key="reports.view", allowed=True)],
    )
    bootstrap = CoreAppBootstrap(session=session)  # type: ignore[arg-type]

    bootstrap.login("alice", "safe-password")
    visible = bootstrap.visible_navigation()

    assert "Reports" in visible
    assert "Stock" not in visible
    assert "Admin/Settings" not in visible


def test_logout_clears_session_and_routes_to_login() -> None:
    session = FakeSession(profile=_profile(), permissions=[PermissionEntry(key="stock.view", allowed=True)])
    bootstrap = CoreAppBootstrap(session=session)  # type: ignore[arg-type]
    bootstrap.login("alice", "safe-password")

    result = bootstrap.logout()

    assert session.token is None
    assert result.route is Route.LOGIN
    assert bootstrap.state.allowed_permissions == set()


def test_login_fails_when_api_is_unreachable() -> None:
    session = FakeSession(
        profile=_profile(),
        permissions=[],
        health_error=RuntimeError("network down"),
    )
    bootstrap = CoreAppBootstrap(session=session)  # type: ignore[arg-type]

    result = bootstrap.login("alice", "safe-password")

    assert result.route is Route.LOGIN
    assert result.error_message == "Cannot connect to ARIS API. Verify network/VPN and try again."


def test_login_fails_when_api_health_is_unhealthy() -> None:
    session = FakeSession(
        profile=_profile(),
        permissions=[],
        health_payload={"ok": False},
    )
    bootstrap = CoreAppBootstrap(session=session)  # type: ignore[arg-type]

    result = bootstrap.login("alice", "safe-password")

    assert result.route is Route.LOGIN
    assert result.error_message == "ARIS API is reachable but unhealthy. Please retry in a moment."
