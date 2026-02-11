from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SafeRetryPanel:
    action: str
    transient_error: bool
    is_mutation: bool
    idempotent: bool

    def can_retry(self) -> bool:
        if not self.transient_error:
            return False
        if self.is_mutation and not self.idempotent:
            return False
        return True

    def render(self) -> dict[str, object]:
        return {
            "action": self.action,
            "enabled": self.can_retry(),
            "reason": None if self.can_retry() else "Retry disabled unless error is transient and operation is safe.",
        }
