from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StatusBar:
    message: str = "Ready"
    tenant_id: str | None = None
    username: str | None = None
    session_state: str = "ANON"

    def set_message(self, message: str) -> None:
        self.message = message

    def set_context(self, *, tenant_id: str | None, username: str | None, session_state: str) -> None:
        self.tenant_id = tenant_id
        self.username = username
        self.session_state = session_state

    def render(self) -> dict[str, str | None]:
        return {
            "message": self.message,
            "tenant_id": self.tenant_id,
            "username": self.username,
            "session_state": self.session_state,
        }
