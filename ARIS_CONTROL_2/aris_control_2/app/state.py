from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SessionState:
    access_token: str | None = None
    refresh_token: str | None = None
    must_change_password: bool = False
    user: dict[str, Any] | None = None

    def is_authenticated(self) -> bool:
        return bool(self.access_token)

    def clear(self) -> None:
        self.access_token = None
        self.refresh_token = None
        self.must_change_password = False
        self.user = None
