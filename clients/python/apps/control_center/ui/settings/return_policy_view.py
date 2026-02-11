from __future__ import annotations

from apps.control_center.services.settings_service import validate_return_policy


class ReturnPolicyForm:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def validate(self) -> dict[str, str]:
        return validate_return_policy(self.payload)
