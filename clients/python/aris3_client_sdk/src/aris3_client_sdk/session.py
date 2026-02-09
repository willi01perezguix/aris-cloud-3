from __future__ import annotations

from dataclasses import dataclass

from .auth_store import AuthStore
from .clients.access_control import AccessControlClient
from .clients.auth import AuthClient
from .clients.health import HealthClient
from .clients.smoke import SmokeClient
from .clients.pos_cash_client import PosCashClient
from .clients.pos_sales_client import PosSalesClient
from .clients.stock_client import StockClient
from .config import ClientConfig
from .http_client import HttpClient
from .models import SessionData, TokenResponse, UserResponse
from .tracing import TraceContext


@dataclass
class ApiSession:
    config: ClientConfig
    auth_store: AuthStore | None = None
    trace: TraceContext | None = None
    token: str | None = None
    user: UserResponse | None = None

    def __post_init__(self) -> None:
        self.auth_store = self.auth_store or AuthStore()
        self.trace = self.trace or TraceContext()
        stored = self.auth_store.load()
        if stored and not self.token:
            self.token = stored.access_token
            self.user = stored.user

    def _http(self) -> HttpClient:
        return HttpClient(config=self.config, trace=self.trace)

    def auth_client(self) -> AuthClient:
        return AuthClient(http=self._http(), access_token=self.token)

    def access_control_client(self) -> AccessControlClient:
        return AccessControlClient(http=self._http(), access_token=self.token)

    def health_client(self) -> HealthClient:
        return HealthClient(http=self._http(), access_token=self.token)

    def smoke_client(self) -> SmokeClient:
        return SmokeClient(self.auth_client(), self.health_client())

    def stock_client(self) -> StockClient:
        return StockClient(http=self._http(), access_token=self.token)

    def pos_sales_client(self) -> PosSalesClient:
        return PosSalesClient(http=self._http(), access_token=self.token)

    def pos_cash_client(self) -> PosCashClient:
        return PosCashClient(http=self._http(), access_token=self.token)

    def establish(self, token: TokenResponse, user: UserResponse | None) -> None:
        self.token = token.access_token
        self.user = user
        self.auth_store.save(SessionData(access_token=self.token, user=self.user, env_name=self.config.env_name))

    def clear(self) -> None:
        self.token = None
        self.user = None
        if self.auth_store:
            self.auth_store.clear()
