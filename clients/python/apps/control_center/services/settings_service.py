from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from aris3_client_sdk.clients.admin_client import AdminClient
from shared.feature_flags.flags import FeatureFlagStore
from shared.feature_flags.provider import DictFlagProvider
from shared.telemetry.events import build_event
from shared.telemetry.logger import TelemetryLogger

from apps.control_center.app.state import OperationRecord, SessionState


@dataclass
class SaveResult:
    payload: dict[str, Any]
    operation: OperationRecord


class SettingsService:
    def __init__(
        self,
        client: AdminClient,
        state: SessionState,
        *,
        flags: FeatureFlagStore | None = None,
        telemetry: TelemetryLogger | None = None,
    ) -> None:
        self.client = client
        self.state = state
        self.flags = flags or FeatureFlagStore(provider=DictFlagProvider(values={}))
        self.telemetry = telemetry or TelemetryLogger(app_name="control_center", enabled=False)

    def load_variant_fields(self) -> dict[str, Any]:
        return self.client._request("GET", "/aris3/admin/settings/variant-fields")

    def save_variant_fields(self, payload: dict[str, Any], *, idempotency_key: str) -> SaveResult:
        response = self.client._request(
            "PATCH",
            "/aris3/admin/settings/variant-fields",
            json=payload,
            headers={"Idempotency-Key": idempotency_key},
        )
        self.telemetry.emit(
            build_event(
                category="api_call_result",
                name="cc_screen_view",
                module="control_center",
                action="settings.variant_fields.save",
                success=True,
                trace_id=response.get("trace_id"),
            )
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
        if value is None:
            continue
        if not isinstance(value, str):
            errors[key] = "Must be a string"
            continue
        if len(value.strip()) == 0:
            errors[key] = "Cannot be empty"
        if len(value) > 255:
            errors[key] = "Must be <= 255 characters"
    return errors


def validate_return_policy(payload: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    if "return_window_days" in payload and int(payload["return_window_days"]) < 0:
        errors["return_window_days"] = "Must be >= 0"
    if "restocking_fee_pct" in payload:
        fee = float(payload["restocking_fee_pct"])
        if fee < 0 or fee > 100:
            errors["restocking_fee_pct"] = "Must be between 0 and 100"
    strategy = payload.get("non_reusable_label_strategy")
    if strategy is not None and strategy not in {"ASSIGN_NEW_EPC", "TO_PENDING"}:
        errors["non_reusable_label_strategy"] = "Unsupported strategy"
    return errors
