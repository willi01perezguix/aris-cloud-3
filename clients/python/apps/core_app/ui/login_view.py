from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LoginView:
    title: str = "ARIS CORE-3 Login"

    def render_message(self) -> str:
        return "Please sign in to continue."
