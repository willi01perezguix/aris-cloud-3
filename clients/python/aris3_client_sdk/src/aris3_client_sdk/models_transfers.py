from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class TransferStatus(str, Enum):
    DRAFT = "DRAFT"
    DISPATCHED = "DISPATCHED"
    RECEIVED = "RECEIVED"
    PARTIAL_RECEIVED = "PARTIAL_RECEIVED"
    CANCELLED = "CANCELLED"


class TransferQuery(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    q: str | None = None
    status: str | None = None
    origin_store_id: str | None = None
    destination_store_id: str | None = None
    from_date: datetime | str | None = Field(default=None, alias="from")
    to_date: datetime | str | None = Field(default=None, alias="to")
    page: int | None = None
    page_size: int | None = None
    sort_by: str | None = None
    sort_order: str | None = Field(default=None, alias="sort_dir")


class TransferLineSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    sku: str | None = None
    description: str | None = None
    var1_value: str | None = None
    var2_value: str | None = None
    epc: str | None = None
    location_code: str | None = None
    pool: str | None = None
    status: str | None = None
    location_is_vendible: bool = True
    image_asset_id: str | None = None
    image_url: str | None = None
    image_thumb_url: str | None = None
    image_source: str | None = None
    image_updated_at: datetime | None = None


class TransferLineCreate(BaseModel):
    model_config = ConfigDict(extra="allow")

    line_type: str
    qty: int = 1
    snapshot: TransferLineSnapshot


class TransferLineResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    line_type: str
    qty: int
    received_qty: int
    outstanding_qty: int
    shortage_status: str | None = None
    resolution_status: str | None = None
    snapshot: TransferLineSnapshot
    created_at: datetime


class TransferHeader(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    tenant_id: str
    origin_store_id: str
    destination_store_id: str
    status: str
    created_by_user_id: str | None = None
    updated_by_user_id: str | None = None
    dispatched_by_user_id: str | None = None
    canceled_by_user_id: str | None = None
    dispatched_at: datetime | None = None
    canceled_at: datetime | None = None
    received_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None


class TransferMovementSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    dispatched_lines: int
    dispatched_qty: int
    pending_reception: bool
    shortages_possible: bool


class TransferMutationLineResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    line_id: str | None = None
    row_index: int | None = None
    status: str | None = None
    code: str | None = None
    message: str | None = None
    details: dict | None = None


class TransferResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    header: TransferHeader
    lines: list[TransferLineResponse]
    movement_summary: TransferMovementSummary
    line_results: list[TransferMutationLineResult] | None = None


class TransferListResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    rows: list[TransferResponse]


class TransferCreateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    transaction_id: str | None = None
    tenant_id: str | None = None
    origin_store_id: str
    destination_store_id: str
    lines: list[TransferLineCreate]


class TransferUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    transaction_id: str | None = None
    tenant_id: str | None = None
    origin_store_id: str | None = None
    destination_store_id: str | None = None
    lines: list[TransferLineCreate] | None = None


class TransferReceiveLine(BaseModel):
    model_config = ConfigDict(extra="allow")

    line_id: str
    qty: int = 1
    location_code: str
    pool: str
    location_is_vendible: bool = True


class TransferShortageLine(BaseModel):
    model_config = ConfigDict(extra="allow")

    line_id: str
    qty: int
    reason_code: str
    notes: str | None = None


class TransferShortageResolutionLine(BaseModel):
    model_config = ConfigDict(extra="allow")

    line_id: str
    qty: int


class TransferShortageResolution(BaseModel):
    model_config = ConfigDict(extra="allow")

    resolution: str
    lines: list[TransferShortageResolutionLine]


class TransferActionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    transaction_id: str | None = None
    tenant_id: str | None = None
    action: str
    receive_lines: list[TransferReceiveLine] | None = None
    shortages: list[TransferShortageLine] | None = None
    resolution: TransferShortageResolution | None = None


class DispatchRequest(TransferActionRequest):
    action: str = "dispatch"


class ReceiveRequest(TransferActionRequest):
    action: str = "receive"
    receive_lines: list[TransferReceiveLine]


class ReportShortagesRequest(TransferActionRequest):
    action: str = "report_shortages"
    shortages: list[TransferShortageLine]


class ResolveShortagesRequest(TransferActionRequest):
    action: str = "resolve_shortages"
    resolution: TransferShortageResolution


class CancelRequest(TransferActionRequest):
    action: str = "cancel"
