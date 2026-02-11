from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionGate:
    key: str
    allowed: bool
    reason: str | None = None


def gate_permission(allowed_permissions: set[str], key: str, *, deny_message: str) -> PermissionGate:
    if key in allowed_permissions:
        return PermissionGate(key=key, allowed=True)
    return PermissionGate(key=key, allowed=False, reason=deny_message)
