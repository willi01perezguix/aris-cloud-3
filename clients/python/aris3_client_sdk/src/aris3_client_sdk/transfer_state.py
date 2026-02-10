from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TransferActionAvailability:
    can_update: bool
    can_dispatch: bool
    can_receive: bool
    can_report_shortages: bool
    can_resolve_shortages: bool
    can_cancel: bool


def transfer_action_availability(
    status: str,
    *,
    can_manage: bool,
    is_destination_user: bool,
) -> TransferActionAvailability:
    if not can_manage:
        return TransferActionAvailability(False, False, False, False, False, False)

    status_value = status.upper() if status else ""
    can_update = status_value == "DRAFT"
    can_dispatch = status_value == "DRAFT"
    can_cancel = status_value in {"DRAFT", "DISPATCHED"}
    can_receive = status_value in {"DISPATCHED", "PARTIAL_RECEIVED"} and is_destination_user
    can_report = status_value in {"DISPATCHED", "PARTIAL_RECEIVED"} and is_destination_user
    can_resolve = status_value in {"DISPATCHED", "PARTIAL_RECEIVED"} and is_destination_user
    return TransferActionAvailability(
        can_update=can_update,
        can_dispatch=can_dispatch,
        can_receive=can_receive,
        can_report_shortages=can_report,
        can_resolve_shortages=can_resolve,
        can_cancel=can_cancel,
    )
