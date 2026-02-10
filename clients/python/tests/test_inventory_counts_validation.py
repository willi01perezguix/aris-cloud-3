from __future__ import annotations

import pytest

from aris3_client_sdk.inventory_counts_validation import (
    ClientValidationError,
    validate_action_state_intent,
    validate_reconcile_payload,
    validate_scan_batch_payload,
    validate_start_payload,
)


def test_validate_start_payload_requires_store_id() -> None:
    with pytest.raises(ClientValidationError):
        validate_start_payload({"store_id": ""})


def test_validate_scan_batch_normalizes_epc_and_rejects_empty() -> None:
    with pytest.raises(ClientValidationError):
        validate_scan_batch_payload({"items": []})

    payload = validate_scan_batch_payload({"items": [{"epc": " abcd ", "qty": 1}]})
    assert payload.items[0].epc == "ABCD"


def test_validate_reconcile_payload() -> None:
    payload = validate_reconcile_payload({})
    assert payload.action == "RECONCILE"


def test_validate_action_state_intent_rejects_invalid_transition() -> None:
    with pytest.raises(ClientValidationError):
        validate_action_state_intent("DRAFT", "CLOSE")
