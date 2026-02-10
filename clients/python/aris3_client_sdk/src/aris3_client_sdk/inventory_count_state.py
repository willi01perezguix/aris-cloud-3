from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InventoryCountActionAvailability:
    can_start: bool
    can_pause: bool
    can_resume: bool
    can_close: bool
    can_cancel: bool
    can_reconcile: bool
    can_scan: bool


def inventory_count_action_availability(state: str, *, can_manage: bool) -> InventoryCountActionAvailability:
    if not can_manage:
        return InventoryCountActionAvailability(False, False, False, False, False, False, False)

    value = (state or "").upper()
    return InventoryCountActionAvailability(
        can_start=value == "DRAFT",
        can_pause=value == "ACTIVE",
        can_resume=value == "PAUSED",
        can_close=value in {"ACTIVE", "PAUSED"},
        can_cancel=value in {"DRAFT", "ACTIVE", "PAUSED"},
        can_reconcile=value == "CLOSED",
        can_scan=value == "ACTIVE",
    )
