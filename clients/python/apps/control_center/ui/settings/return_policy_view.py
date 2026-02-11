from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from apps.control_center.services.settings_service import validate_return_policy


@dataclass
class ReturnPolicyForm:
    payload: dict
    _last_saved: dict = field(default_factory=dict)
    last_saved_at: str | None = None

    def validate(self) -> dict[str, str]:
        return validate_return_policy(self.payload)

    def validation_summary(self) -> str | None:
        errors = self.validate()
        if not errors:
            return None
        return f"Please fix {len(errors)} return policy validation issue(s)."

    def mark_saved(self) -> None:
        self._last_saved = dict(self.payload)
        self.last_saved_at = datetime.now(timezone.utc).isoformat()

    def restore_last_saved(self) -> bool:
        if not self._last_saved:
            return False
        self.payload = dict(self._last_saved)
        return True

    def has_unsaved_changes(self) -> bool:
        if not self._last_saved:
            return bool(self.payload)
        return self.payload != self._last_saved
