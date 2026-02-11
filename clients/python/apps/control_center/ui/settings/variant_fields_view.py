from __future__ import annotations

from apps.control_center.services.settings_service import validate_variant_fields


class VariantFieldsForm:
    def __init__(self, var1_label: str | None = None, var2_label: str | None = None) -> None:
        self.var1_label = var1_label
        self.var2_label = var2_label

    def to_payload(self) -> dict[str, str | None]:
        return {"var1_label": self.var1_label, "var2_label": self.var2_label}

    def validate(self) -> dict[str, str]:
        return validate_variant_fields(self.to_payload())
