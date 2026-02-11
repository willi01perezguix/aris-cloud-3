from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from aris3_client_sdk.clients.admin_client import AdminClient

from apps.control_center.app.state import OperationRecord, SessionState


@dataclass
class SaveResult:
    payload: dict[str, Any]
    operation: OperationRecord


class SettingsService:
    def __init__(self, client: AdminClient, state: SessionState) -> None:
        self.client = client
        self.state = state

    def load_variant_fields(self) -> dict[str, Any]:
        return self.client._request("GET", "/aris3/admin/settings/variant-fields")

    def save_variant_fields(self, payload: dict[str, Any], *, idempotency_key: str) -> SaveResult:
        response = self.client._request(
            "PATCH",
            "/aris3/admin/settings/variant-fields",
            json=payload,
            headers={"Idempotency-Key": idempotency_key},
        )
        return SaveResult(payload=response, operation=self._record("admin.settings.variant_fields.update", "settings:variant-fields", response, idempotency_key=idempotency_key))

    def load_return_policy(self) -> dict[str, Any]:
        return self.client._request("GET", "/aris3/admin/settings/return-policy")

    def save_return_policy(self, payload: dict[str, Any], *, idempotency_key: str) -> SaveResult:
        response = self.client._request(
            "PATCH",
            "/aris3/admin/settings/return-policy",
            json=payload,
            headers={"Idempotency-Key": idempotency_key},
        )
        return SaveResult(payload=response, operation=self._record("admin.settings.return_policy.update", "settings:return-policy", response, idempotency_key=idempotency_key))

    def _record(self, action: str, target: str, payload: dict[str, Any], *, idempotency_key: str) -> OperationRecord:
        operation = OperationRecord(
            actor=self.state.actor or "unknown",
            target=target,
            action=action,
            at=datetime.now(timezone.utc),
            trace_id=payload.get("trace_id"),
            idempotency_key=idempotency_key,
        )
        self.state.add_operation(operation)
        return operation


def validate_variant_fields(payload: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    for key in ("var1_label", "var2_label"):
        value = payload.get(key)
        if value is not None and isinstance(value, str) and len(value) > 255:
            errors[key] = "Must be <= 255 characters"
    return errors


def validate_return_policy(payload: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    if "return_window_days" in payload and int(payload["return_window_days"]) < 0:
        errors["return_window_days"] = "Must be >= 0"
    if "restocking_fee_pct" in payload and float(payload["restocking_fee_pct"]) < 0:
        errors["restocking_fee_pct"] = "Must be >= 0"
    strategy = payload.get("non_reusable_label_strategy")
    if strategy is not None and strategy not in {"ASSIGN_NEW_EPC", "TO_PENDING"}:
        errors["non_reusable_label_strategy"] = "Unsupported strategy"
    return errors
