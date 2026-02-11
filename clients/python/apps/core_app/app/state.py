from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from aris3_client_sdk.models import UserResponse


class Route(str, Enum):
    LOGIN = "login"
    CHANGE_PASSWORD = "change_password"
    SHELL = "shell"


@dataclass
class SessionContext:
    user: UserResponse | None = None
    tenant_id: str | None = None
    store_id: str | None = None


@dataclass
class AppState:
    route: Route = Route.LOGIN
    error_message: str | None = None
    status_message: str = "Ready"
    trace_id: str | None = None
    session: SessionContext = field(default_factory=SessionContext)
    allowed_permissions: set[str] = field(default_factory=set)
