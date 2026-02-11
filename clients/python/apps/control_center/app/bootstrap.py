from __future__ import annotations

from aris3_client_sdk import ApiSession, ClientConfig, load_config
from aris3_client_sdk.clients.access_control import AccessControlClient
from aris3_client_sdk.clients.admin_client import AdminClient
from aris3_client_sdk.clients.auth import AuthClient

from apps.control_center.app.state import ControlCenterState
from apps.control_center.services.access_control_service import AccessControlService
from apps.control_center.services.admin_users_service import AdminUsersService
from apps.control_center.services.settings_service import SettingsService


class ControlCenterBootstrap:
    def __init__(self, config: ClientConfig | None = None, session: ApiSession | None = None) -> None:
        self.config = config or load_config()
        self.session = session or ApiSession(self.config)
        self.state = ControlCenterState()

    def login(self, username: str, password: str) -> None:
        auth = AuthClient(http=self.session._http())
        token = auth.login(username, password)
        auth_token = AuthClient(http=self.session._http(), access_token=token.access_token)
        user = auth_token.me()
        self.session.establish(token, user)
        self.state.session.actor = user.username
        self.state.session.tenant_id = user.tenant_id
        access = AccessControlClient(http=self.session._http(), access_token=token.access_token)
        decisions = access.effective_permissions()
        self.state.session.allowed_permissions = {entry.key for entry in decisions.permissions if entry.allowed}

    def services(self) -> tuple[AdminUsersService, AccessControlService, SettingsService]:
        token = self.session.access_token
        admin = AdminClient(http=self.session._http(), access_token=token)
        access = AccessControlClient(http=self.session._http(), access_token=token)
        return (
            AdminUsersService(admin, self.state.session),
            AccessControlService(access, admin, self.state.session),
            SettingsService(admin, self.state.session),
        )
