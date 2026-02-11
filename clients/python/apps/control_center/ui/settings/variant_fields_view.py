from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from apps.control_center.services.settings_service import validate_variant_fields


@dataclass
class VariantFieldsForm:
    var1_label: str | None = None
    var2_label: str | None = None
    _last_saved: dict[str, str | None] | None = None
    last_saved_at: str | None = None

    def to_payload(self) -> dict[str, str | None]:
        return {"var1_label": self.var1_label, "var2_label": self.var2_label}

    def validate(self) -> dict[str, str]:
        return validate_variant_fields(self.to_payload())

    def validation_summary(self) -> str | None:
        errors = self.validate()
        if not errors:
            return None
        return f"Please fix {len(errors)} field validation issue(s)."

    def mark_saved(self) -> None:
        self._last_saved = self.to_payload()
        self.last_saved_at = datetime.now(timezone.utc).isoformat()

    def restore_last_saved(self) -> bool:
        if not self._last_saved:
            return False
        self.var1_label = self._last_saved.get("var1_label")
        self.var2_label = self._last_saved.get("var2_label")
        return True

    def has_unsaved_changes(self) -> bool:
        if self._last_saved is None:
            return bool(self.var1_label or self.var2_label)
        return self.to_payload() != self._last_saved
