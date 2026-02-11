from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CashStatusChip:
    session_payload: dict[str, Any] | None

    def render(self) -> dict[str, Any]:
        status = (self.session_payload or {}).get("status")
        return {
            "label": "Cash OPEN" if status == "OPEN" else "Cash CLOSED",
            "status": status or "NONE",
            "is_open": status == "OPEN",
            "session_id": (self.session_payload or {}).get("id"),
        }
