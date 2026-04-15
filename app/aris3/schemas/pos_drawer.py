from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.aris3.schemas.pos_common import PosBaseModel


DrawerMovementType = Literal["CHECKOUT", "CASH_IN", "CASH_OUT", "MANUAL", "TEST", "UNKNOWN"]
DrawerEventType = Literal[
    "CHECKOUT_CASH_DRAWER_OPEN",
    "CHECKOUT_CASH_DRAWER_OPEN_FAILED",
    "CHECKOUT_PRINT_CASH_DRAWER_OPEN",
    "CASH_IN_DRAWER_OPEN",
    "CASH_OUT_DRAWER_OPEN",
    "MANUAL_DRAWER_OPEN",
    "TEST_DRAWER_OPEN",
    "DRAWER_CLOSE_CONFIRMED",
]
DrawerResult = Literal["SUCCESS", "FAILED"]


class DrawerEventCreateRequest(PosBaseModel):
    tenant_id: str | None = Field(
        default=None,
        description="Tenant scope. Required for superadmin roles; ignored/validated against token for tenant-scoped roles.",
    )
    store_id: str | None = Field(default=None, description="Store scope. Optional for broad roles, inferred from token when bound.")
    terminal_id: str | None = None
    cash_session_id: str | None = None
    sale_id: str | None = None
    movement_type: DrawerMovementType = "UNKNOWN"
    event_type: DrawerEventType
    reason: str | None = Field(default=None, max_length=500)
    printer_name: str | None = Field(default=None, max_length=255)
    machine_name: str | None = Field(default=None, max_length=255)
    requested_at: datetime | None = None
    executed_at: datetime | None = None
    closed_confirmed_at: datetime | None = None
    result: DrawerResult
    details_json: dict | None = None
    trace_id: str | None = Field(default=None, max_length=255)


class DrawerEventConfirmCloseRequest(PosBaseModel):
    tenant_id: str | None = Field(
        default=None,
        description="Tenant scope. Required for superadmin roles; ignored/validated against token for tenant-scoped roles.",
    )
    store_id: str | None = None
    closed_confirmed_at: datetime | None = None
    trace_id: str | None = Field(default=None, max_length=255)


class DrawerEventResponse(PosBaseModel):
    id: str
    tenant_id: str
    store_id: str
    terminal_id: str | None = None
    user_id: str | None = None
    cash_session_id: str | None = None
    sale_id: str | None = None
    movement_type: str
    event_type: str
    reason: str | None = None
    printer_name: str | None = None
    machine_name: str | None = None
    requested_at: datetime | None = None
    executed_at: datetime | None = None
    closed_confirmed_at: datetime | None = None
    result: str
    details_json: dict | None = None
    trace_id: str | None = None
    created_at: datetime
