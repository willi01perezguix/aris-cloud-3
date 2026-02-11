from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPanel:
    operation: str
    is_mutation: bool
    idempotent: bool
    has_transient_error: bool

    def can_retry(self) -> bool:
        if self.is_mutation and not self.idempotent:
            return False
        return self.has_transient_error

    def render(self) -> dict[str, object]:
        return {
            "operation": self.operation,
            "enabled": self.can_retry(),
            "warning": None
            if self.can_retry()
            else "Retry disabled for non-idempotent/unsafe operation.",
        }
