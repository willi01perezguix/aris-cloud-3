from __future__ import annotations

from aris3_client_sdk.inventory_count_state import inventory_count_action_availability


def test_inventory_action_availability() -> None:
    availability = inventory_count_action_availability("ACTIVE", can_manage=True)
    assert availability.can_pause is True
    assert availability.can_resume is False
    assert availability.can_scan is True


def test_inventory_action_availability_permission_gate() -> None:
    availability = inventory_count_action_availability("ACTIVE", can_manage=False)
    assert availability.can_pause is False
    assert availability.can_close is False
