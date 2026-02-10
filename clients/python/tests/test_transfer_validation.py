from __future__ import annotations

import pytest

from aris3_client_sdk.stock_validation import ClientValidationError
from aris3_client_sdk.transfer_state import transfer_action_availability
from aris3_client_sdk.transfer_validation import (
    validate_create_transfer_payload,
    validate_receive_payload,
    validate_shortage_resolution_payload,
)


def test_validate_create_transfer_payload_origin_destination_must_differ() -> None:
    payload = {
        "origin_store_id": "store-1",
        "destination_store_id": "store-1",
        "lines": [
            {
                "line_type": "SKU",
                "qty": 1,
                "snapshot": {"sku": "SKU-1", "location_code": "LOC", "pool": "P1", "location_is_vendible": True},
            }
        ],
    }
    with pytest.raises(ClientValidationError):
        validate_create_transfer_payload(payload)


def test_validate_receive_payload_qty_exceeds_expectation() -> None:
    payload = {
        "receive_lines": [
            {"line_id": "line-1", "qty": 3, "location_code": "LOC", "pool": "P1", "location_is_vendible": True}
        ]
    }
    with pytest.raises(ClientValidationError):
        validate_receive_payload(payload, line_expectations={"line-1": 2}, line_types={"line-1": "SKU"})


def test_validate_shortage_resolution_role_gate() -> None:
    payload = {
        "resolution": {
            "resolution": "LOST_IN_ROUTE",
            "lines": [{"line_id": "line-1", "qty": 1}],
        }
    }
    with pytest.raises(ClientValidationError):
        validate_shortage_resolution_payload(payload, allow_lost_in_route=False)


def test_transfer_action_availability_by_state() -> None:
    availability = transfer_action_availability("DRAFT", can_manage=True, is_destination_user=False)
    assert availability.can_dispatch is True
    assert availability.can_receive is False
