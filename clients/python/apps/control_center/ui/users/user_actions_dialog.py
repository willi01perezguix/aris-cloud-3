from __future__ import annotations

from dataclasses import dataclass, field

from apps.control_center.ui.shared.notification_center import AdminNotificationCenter

HIGH_IMPACT_ACTIONS = {"set_status", "set_role", "reset_password"}


def requires_confirmation(action: str) -> bool:
    return action in HIGH_IMPACT_ACTIONS


def action_dedupe_key(user_id: str, action: str, transaction_id: str | None = None) -> str:
    return f"{user_id}:{action}:{transaction_id or 'no-txn'}"


@dataclass
class UserActionGuard:
    user_id: str
    action: str
    reason: str | None = None
    in_flight: bool = False
    _submitted_keys: set[str] = field(default_factory=set)
    notifications: AdminNotificationCenter = field(default_factory=AdminNotificationCenter)

    def target_summary(self) -> str:
        return f"target={self.user_id} action={self.action}"

    def can_submit(self, dedupe_key: str) -> bool:
        return not self.in_flight and dedupe_key not in self._submitted_keys

    def mark_submitted(self, dedupe_key: str) -> None:
        self.in_flight = True
        self._submitted_keys.add(dedupe_key)

    def complete(self, *, success: bool, trace_id: str | None = None) -> None:
        self.in_flight = False
        self.notifications.toast(
            level="success" if success else "error",
            message="User action completed" if success else "User action failed",
            trace_id=trace_id,
            details={"target": self.target_summary(), "reason": self.reason},
        )
