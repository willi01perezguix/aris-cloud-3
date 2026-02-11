from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ChangePasswordView:
    title: str = "Change Password"

    def render_message(self) -> str:
        return "Password update required before entering ARIS CORE-3 shell."
