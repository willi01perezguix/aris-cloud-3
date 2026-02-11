from __future__ import annotations

from dataclasses import dataclass

from shared.feature_flags.flags import FeatureFlagStore
from shared.feature_flags.provider import DictFlagProvider
from shared.telemetry.events import build_event

from apps.control_center.app.state import SessionState
from apps.control_center.services.settings_service import SettingsService
from apps.control_center.ui.settings.return_policy_view import ReturnPolicyForm
from apps.control_center.ui.settings.variant_fields_view import VariantFieldsForm


@dataclass
class FakeAdminClient:
    def _request(self, method: str, path: str, **kwargs):
        if path.endswith("variant-fields") and method == "PATCH":
            return {**kwargs["json"], "trace_id": "trace-vf"}
        if path.endswith("return-policy") and method == "PATCH":
            return {**kwargs["json"], "trace_id": "trace-rp"}
        if path.endswith("variant-fields") and method == "GET":
            return {"var1_label": "Color", "var2_label": "Size", "trace_id": "trace-vf-get"}
        if path.endswith("return-policy") and method == "GET":
            return {"return_window_days": 30, "restocking_fee_pct": 0, "non_reusable_label_strategy": "ASSIGN_NEW_EPC"}
        return {"trace_id": "trace-generic"}


def test_settings_validation_unsaved_changes_and_restore() -> None:
    form = VariantFieldsForm(var1_label="", var2_label="Size")
    assert "var1_label" in form.validate()
    assert form.validation_summary() is not None
    form.var1_label = "Color"
    form.mark_saved()
    form.var1_label = "Shade"
    assert form.has_unsaved_changes() is True
    assert form.restore_last_saved() is True
    assert form.var1_label == "Color"


def test_return_policy_validation_and_unsaved_changes() -> None:
    form = ReturnPolicyForm(payload={"restocking_fee_pct": 120, "non_reusable_label_strategy": "BAD"})
    assert "restocking_fee_pct" in form.validate()
    assert "non_reusable_label_strategy" in form.validate()
    form.payload = {"restocking_fee_pct": 5, "non_reusable_label_strategy": "ASSIGN_NEW_EPC"}
    form.mark_saved()
    form.payload["restocking_fee_pct"] = 10
    assert form.has_unsaved_changes() is True
    assert form.restore_last_saved() is True


def test_telemetry_shape_and_feature_flag_gating_behavior() -> None:
    flags = FeatureFlagStore(provider=DictFlagProvider(values={"cc_rbac_editor_v2": True}))
    assert flags.enabled("cc_rbac_editor_v2") is True
    assert flags.ensure_permission_gate(permission_allowed=False) is False
    event = build_event(
        category="api_call_result",
        name="cc_validation_failed",
        module="control_center",
        action="settings.return_policy.save",
        context={"field_count": 2},
    )
    payload = event.to_dict()
    assert payload["name"] == "cc_validation_failed"
    assert "field_count" in payload["context"]


def test_settings_service_save_with_idempotency() -> None:
    service = SettingsService(FakeAdminClient(), SessionState(actor="admin"))  # type: ignore[arg-type]
    saved = service.save_variant_fields({"var1_label": "Color"}, idempotency_key="idem-1")
    assert saved.operation.idempotency_key == "idem-1"
