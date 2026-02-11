from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StatusBar:
    message: str = "Ready"

    def set_message(self, message: str) -> None:
        self.message = message
