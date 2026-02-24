from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


_TRANSFER_LINE_SNAPSHOT_EXAMPLE = {
    "sku": "SKU-1",
    "description": "Blue Jacket",
    "var1_value": "Blue",
    "var2_value": "L",
    "cost_price": 25.0,
    "suggested_price": 35.0,
    "sale_price": 32.5,
    "epc": "ABCDEFABCDEFABCDEFABCDEF",
    "location_code": "WH-MAIN",
    "pool": "BODEGA",
    "status": "RFID",
    "location_is_vendible": False,
    "image_asset_id": None,
    "image_url": None,
    "image_thumb_url": None,
    "image_source": None,
    "image_updated_at": None,
}


class TransferLineSnapshot(BaseModel):
    sku: str | None
    description: str | None
    var1_value: str | None
    var2_value: str | None
    cost_price: float | None = None
    suggested_price: float | None = None
    sale_price: float | None = None
    epc: str | None
    location_code: str | None
    pool: str | None
    status: str | None
    location_is_vendible: bool
    image_asset_id: UUID | None
    image_url: str | None
    image_thumb_url: str | None
    image_source: str | None
    image_updated_at: datetime | None

    model_config = {"json_schema_extra": {"example": _TRANSFER_LINE_SNAPSHOT_EXAMPLE}}


class TransferLineCreate(BaseModel):
    line_type: Literal["EPC", "SKU"]
    qty: int = 1
    snapshot: TransferLineSnapshot


class TransferLineResponse(BaseModel):
    id: str
    line_type: str
    qty: int
    received_qty: int
    outstanding_qty: int
    shortage_status: str
    resolution_status: str
    snapshot: TransferLineSnapshot
    created_at: datetime


class TransferCreateRequest(BaseModel):
    transaction_id: str | None
    tenant_id: str | None = None
    origin_store_id: str
    destination_store_id: str
    lines: list[TransferLineCreate]


class TransferUpdateRequest(BaseModel):
    transaction_id: str | None
    tenant_id: str | None = None
    origin_store_id: str | None = None
    destination_store_id: str | None = None
    lines: list[TransferLineCreate] | None = None


class TransferReceiveLine(BaseModel):
    line_id: str
    qty: int = 1
    location_code: str | None = None
    pool: str | None = None
    location_is_vendible: bool | None = None


class TransferShortageLine(BaseModel):
    line_id: str
    qty: int
    reason_code: str
    notes: str | None = None


class TransferShortageResolutionLine(BaseModel):
    line_id: str
    qty: int


class TransferShortageResolution(BaseModel):
    resolution: Literal["FOUND_AND_RESEND", "LOST_IN_ROUTE"]
    lines: list[TransferShortageResolutionLine]


class TransferActionRequest(BaseModel):
    transaction_id: str | None
    tenant_id: str | None = None
    action: Literal["dispatch", "cancel", "receive", "report_shortages", "resolve_shortages"]
    receive_lines: list[TransferReceiveLine] | None = None
    shortages: list[TransferShortageLine] | None = None
    resolution: TransferShortageResolution | None = None


class TransferHeaderResponse(BaseModel):
    id: str
    tenant_id: str
    origin_store_id: str
    destination_store_id: str
    status: str
    created_by_user_id: str | None
    updated_by_user_id: str | None
    dispatched_by_user_id: str | None
    canceled_by_user_id: str | None
    dispatched_at: datetime | None
    canceled_at: datetime | None
    received_at: datetime | None
    created_at: datetime
    updated_at: datetime | None


class TransferMovementSummary(BaseModel):
    dispatched_lines: int
    dispatched_qty: int
    pending_reception: bool
    shortages_possible: bool


class TransferResponse(BaseModel):
    header: TransferHeaderResponse
    lines: list[TransferLineResponse]
    movement_summary: TransferMovementSummary


class TransferListResponse(BaseModel):
    rows: list[TransferResponse]
