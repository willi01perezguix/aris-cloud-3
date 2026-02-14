from __future__ import annotations

import logging
from dataclasses import dataclass
from time import perf_counter

from aris3_client_sdk import ApiSession, ClientConfig, load_config, new_idempotency_keys, to_user_facing_error
from aris3_client_sdk.exceptions import ApiError
from aris3_client_sdk.exceptions import MustChangePasswordError
from aris3_client_sdk.models import TokenResponse

from app.navigation import MODULE_SPECS, allowed_modules
from app.state import AppState, Route
from services.auth_service import AuthService
from services.permissions_service import PermissionGate, PermissionsService
from services.profile_service import ProfileService
from ui.shell_view import ShellPlaceholder
from shared.feature_flags.flags import FeatureFlagStore
from shared.feature_flags.provider import DictFlagProvider
from shared.telemetry.events import build_event
from shared.telemetry.logger import TelemetryLogger
from ui.widgets.permissioned_menu import PermissionedMenu

logger = logging.getLogger(__name__)


@dataclass
class BootstrapResult:
    route: Route
    error_message: str | None = None


class CoreAppBootstrap:
    def __init__(self, config: ClientConfig | None = None, session: ApiSession | None = None) -> None:
        self.config = config or load_config()
        self.session = session or ApiSession(self.config)
        self.state = AppState()
        self.auth_service = AuthService(self.session)
        self.profile_service = ProfileService(self.session)
        self.permissions_service = PermissionsService(self.session)
        self.flags = FeatureFlagStore(provider=DictFlagProvider(values={}))
        self.telemetry = TelemetryLogger(app_name="core_app", enabled=False)

    def start(self) -> BootstrapResult:
        if not self.auth_service.has_active_session():
            self._navigate(Route.LOGIN, "No active session")
            return BootstrapResult(route=self.state.route)
        return self._load_authenticated_shell()

    def login(self, username: str, password: str) -> BootstrapResult:
        started = perf_counter()
        try:
            token = self.auth_service.login(username, password)
        except MustChangePasswordError as exc:
            self.state.error_message = self._friendly_error(exc)
            self._emit_auth_result(False, duration_ms=int((perf_counter()-started)*1000), trace_id=getattr(exc, "trace_id", None))
            self._navigate(Route.CHANGE_PASSWORD, "Password update required")
            return BootstrapResult(route=self.state.route, error_message=self.state.error_message)
        except Exception as exc:
            self.state.error_message = self._friendly_error(exc)
            self._emit_auth_result(False, duration_ms=int((perf_counter()-started)*1000), trace_id=getattr(exc, "trace_id", None))
            self._navigate(Route.LOGIN, "Authentication failed")
            return BootstrapResult(route=self.state.route, error_message=self.state.error_message)

        self.session.establish(token=token, user=None)
        self._emit_auth_result(True, duration_ms=int((perf_counter()-started)*1000), trace_id=getattr(token, "trace_id", None))
        return self._load_authenticated_shell()

    def change_password(self, current_password: str, new_password: str) -> BootstrapResult:
        keys = new_idempotency_keys("change-password")
        try:
            token: TokenResponse = self.auth_service.change_password(
                current_password=current_password,
                new_password=new_password,
                idempotency_key=keys.idempotency_key,
            )
            self.session.establish(token=token, user=self.session.user)
        except Exception as exc:
            self.state.error_message = self._friendly_error(exc)
            self._navigate(Route.CHANGE_PASSWORD, "Change password failed")
            return BootstrapResult(route=self.state.route, error_message=self.state.error_message)
        return self._load_authenticated_shell()

    def logout(self) -> BootstrapResult:
        self.auth_service.logout()
        self.state.allowed_permissions.clear()
        self.state.session.user = None
        self.state.session.tenant_id = None
        self.state.session.store_id = None
        self._navigate(Route.LOGIN, "Session cleared")
        return BootstrapResult(route=self.state.route)

    def _load_authenticated_shell(self) -> BootstrapResult:
        try:
            self.state.status_message = "Checking API connectivity..."
            self._ensure_api_connectivity()
            self.state.status_message = "Loading profile..."
            profile = self.profile_service.load_profile()
            self.state.trace_id = profile.trace_id
            self.state.session.user = profile
            self.state.session.tenant_id = profile.tenant_id
            self.state.session.store_id = profile.store_id
            self.session.user = profile

            if profile.must_change_password:
                self._navigate(Route.CHANGE_PASSWORD, "Password update required")
                return BootstrapResult(route=self.state.route)

            effective_permissions = self.permissions_service.load_effective_permissions()
            gate = PermissionGate(effective_permissions.permissions)
            self.state.allowed_permissions = gate.allowed_keys()
            self._navigate(Route.SHELL, "Authenticated")
            self._emit_screen_view("shell", trace_id=effective_permissions.trace_id)
            self.state.error_message = None
            logger.info("shell_ready", extra={"trace_id": effective_permissions.trace_id})
            return BootstrapResult(route=self.state.route)
        except Exception as exc:
            self.state.error_message = self._friendly_error(exc)
            self._navigate(Route.LOGIN, "Failed to initialize shell")
            return BootstrapResult(route=self.state.route, error_message=self.state.error_message)

    def _ensure_api_connectivity(self) -> None:
        health_client_factory = getattr(self.session, "health_client", None)
        if not callable(health_client_factory):
            return
        try:
            payload = health_client_factory().health() or {}
        except Exception as exc:
            raise RuntimeError("Cannot connect to ARIS API. Verify network/VPN and try again.") from exc
        if payload.get("ok") is False:
            raise RuntimeError("ARIS API is reachable but unhealthy. Please retry in a moment.")

    def visible_navigation(self) -> list[str]:
        gate = PermissionGate([{"key": key, "allowed": True} for key in self.state.allowed_permissions])
        menu = PermissionedMenu(list(MODULE_SPECS), gate)
        return menu.visible_labels()

    def placeholders(self) -> list[dict[str, str | tuple[str, ...] | None]]:
        gate = PermissionGate([{"key": key, "allowed": True} for key in self.state.allowed_permissions])
        modules = allowed_modules(gate)
        return [ShellPlaceholder(module=module, session=self.state.session).render() for module in modules]

    @staticmethod
    def _friendly_error(exc: Exception) -> str:
        if isinstance(exc, ApiError):
            return to_user_facing_error(exc)
        return str(exc) or "Unexpected client error"


    def _emit_auth_result(self, success: bool, *, duration_ms: int, trace_id: str | None) -> None:
        if not self.flags.enabled("telemetry_core_app_v1", default=False):
            return
        self.telemetry.emit(
            build_event(
                category="auth",
                name="auth_login_result",
                module="auth",
                action="login",
                success=success,
                duration_ms=duration_ms,
                trace_id=trace_id,
            )
        )

    def _emit_screen_view(self, action: str, *, trace_id: str | None = None) -> None:
        if not self.flags.enabled("telemetry_core_app_v1", default=False):
            return
        self.telemetry.emit(
            build_event(
                category="navigation",
                name="screen_view",
                module="core_app",
                action=action,
                trace_id=trace_id,
                success=True,
            )
        )

    def _navigate(self, route: Route, status_message: str) -> None:
        logger.info("navigation", extra={"route": route.value})
        self.state.route = route
        self.state.status_message = status_message
