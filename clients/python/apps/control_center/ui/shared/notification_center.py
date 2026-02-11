from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AdminNotificationCenter:
    items: list[dict[str, Any]] = field(default_factory=list)

    def toast(self, *, level: str, message: str, trace_id: str | None = None, details: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {"level": level, "message": message, "trace_id": trace_id, "details": details or {}}
        self.items.append(payload)
        return payload

    def render(self) -> dict[str, Any]:
        return {"count": len(self.items), "messages": list(self.items)}

    def clear(self) -> None:
        self.items.clear()
