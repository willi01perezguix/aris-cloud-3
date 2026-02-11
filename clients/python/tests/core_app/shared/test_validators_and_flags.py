from __future__ import annotations

from decimal import Decimal

from shared.feature_flags.flags import FeatureFlagStore
from shared.feature_flags.provider import DictFlagProvider
from ui.shared.validators import validate_import_epc_lines, validate_import_sku_lines, validate_payments


def test_validation_blocks_invalid_forms_with_messages() -> None:
    epc = validate_import_epc_lines([{"epc": "bad", "qty": 2}])
    sku = validate_import_sku_lines([{"sku": "", "qty": 0}])
    pay = validate_payments([{"method": "CARD", "amount": "20.00"}], Decimal("30.00"))

    assert epc.ok is False
    assert "24 HEX" in epc.summary[0]
    assert sku.ok is False
    assert any("positive" in msg for msg in sku.summary)
    assert pay.ok is False
    assert any("authorization_code" in key for key in pay.field_errors)
    assert "totals.missing_amount" in pay.field_errors


def test_feature_flag_gating_behavior_defaults_safe_off() -> None:
    flags = FeatureFlagStore(provider=DictFlagProvider(values={}))
    enabled = FeatureFlagStore(provider=DictFlagProvider(values={"improved_error_presenter_v2": True}))

    assert flags.enabled("improved_error_presenter_v2", default=False) is False
    assert enabled.enabled("improved_error_presenter_v2", default=False) is True
