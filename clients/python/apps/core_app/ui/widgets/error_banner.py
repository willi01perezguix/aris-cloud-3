from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ErrorBanner:
    message: str | None = None

    def show(self, message: str) -> None:
        self.message = message

    def clear(self) -> None:
        self.message = None
