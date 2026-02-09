from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class TransferLineSnapshot(BaseModel):
    sku: str | None
    description: str | None
    var1_value: str | None
    var2_value: str | None
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


class TransferLineCreate(BaseModel):
    line_type: Literal["EPC", "SKU"]
    qty: int = 1
    snapshot: TransferLineSnapshot


class TransferLineResponse(BaseModel):
    id: str
    line_type: str
    qty: int
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


class TransferActionRequest(BaseModel):
    transaction_id: str | None
    tenant_id: str | None = None
    action: Literal["dispatch", "cancel"]


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
