from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ui.shared.view_state import ViewState


@dataclass(frozen=True)
class StateWidget:
    state: ViewState

    def render(self) -> dict[str, Any]:
        payload = self.state.render()
        payload["icon"] = {
            "loading": "spinner",
            "empty": "inbox",
            "success": "check",
            "partial_error": "warning",
            "fatal_error": "error",
            "no_permission": "lock",
        }[payload["status"]]
        return payload
