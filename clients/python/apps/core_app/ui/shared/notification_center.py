from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NotificationCenter:
    messages: list[dict[str, Any]] = field(default_factory=list)

    def push(self, *, level: str, title: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {
            "level": level,
            "title": title,
            "message": message,
            "details": details or {},
        }
        self.messages.append(payload)
        return payload

    def clear(self) -> None:
        self.messages.clear()

    def render(self) -> dict[str, Any]:
        return {"count": len(self.messages), "messages": list(self.messages)}
