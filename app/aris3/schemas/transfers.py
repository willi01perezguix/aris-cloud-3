from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field


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
    line_type: Literal["EPC", "SKU"] = Field(
        description="Transfer line type. Use EPC for RFID-tagged items and SKU for quantity-based stock (PENDING or RFID without EPC)."
    )
    qty: int = 1
    snapshot: TransferLineSnapshot

    model_config = {"extra": "forbid"}


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
    tenant_id: str | None = Field(default=None, json_schema_extra={"deprecated": True})
    origin_store_id: str
    destination_store_id: str
    lines: list[TransferLineCreate] = Field(description="Transfer lines. Supports EPC/RFID and SKU/no-EPC lines with PENDING or RFID status.")

    model_config = {
        "extra": "forbid",
        "json_schema_extra": {
            "example": {
                "transaction_id": "txn-transfer-create-1",
                "origin_store_id": "11111111-1111-1111-1111-111111111111",
                "destination_store_id": "22222222-2222-2222-2222-222222222222",
                "lines": [
                    {
                        "line_type": "EPC",
                        "qty": 1,
                        "snapshot": _TRANSFER_LINE_SNAPSHOT_EXAMPLE,
                    }
                ],
            }
        }
    }


class TransferUpdateRequest(BaseModel):
    transaction_id: str | None
    tenant_id: str | None = Field(default=None, json_schema_extra={"deprecated": True})
    origin_store_id: str | None = None
    destination_store_id: str | None = None
    lines: list[TransferLineCreate] | None = Field(
        default=None,
        description="Replacement transfer lines for draft update. Supports EPC/RFID and SKU/no-EPC lines with PENDING or RFID status.",
    )

    model_config = {
        "extra": "forbid",
        "json_schema_extra": {
            "example": {
                "transaction_id": "txn-transfer-update-1",
                "lines": [
                    {
                        "line_type": "EPC",
                        "qty": 1,
                        "snapshot": _TRANSFER_LINE_SNAPSHOT_EXAMPLE,
                    }
                ],
            }
        },
    }


class TransferReceiveLine(BaseModel):
    line_id: str
    qty: int = 1
    location_code: str | None = None
    pool: str | None = None
    location_is_vendible: bool | None = None

    model_config = {"extra": "forbid"}


class TransferShortageLine(BaseModel):
    line_id: str
    qty: int
    reason_code: str
    notes: str | None = None

    model_config = {"extra": "forbid"}


class TransferShortageResolutionLine(BaseModel):
    line_id: str
    qty: int

    model_config = {"extra": "forbid"}


class TransferShortageResolution(BaseModel):
    resolution: Literal["FOUND_AND_RESEND", "LOST_IN_ROUTE"]
    lines: list[TransferShortageResolutionLine]

    model_config = {"extra": "forbid"}


class TransferDispatchActionRequest(BaseModel):
    transaction_id: str | None
    tenant_id: str | None = Field(default=None, json_schema_extra={"deprecated": True})
    action: Literal["dispatch"]
    model_config = {"extra": "forbid", "json_schema_extra": {"example": {"transaction_id": "txn-dispatch-1", "action": "dispatch"}}}


class TransferCancelActionRequest(BaseModel):
    transaction_id: str | None
    tenant_id: str | None = Field(default=None, json_schema_extra={"deprecated": True})
    action: Literal["cancel"]
    model_config = {"extra": "forbid", "json_schema_extra": {"example": {"transaction_id": "txn-cancel-1", "action": "cancel"}}}


class TransferReceiveActionRequest(BaseModel):
    transaction_id: str | None
    tenant_id: str | None = Field(default=None, json_schema_extra={"deprecated": True})
    action: Literal["receive"]
    receive_lines: list[TransferReceiveLine] | None = None

    model_config = {
        "extra": "forbid",
        "json_schema_extra": {
            "example": {
                "transaction_id": "txn-receive-1",
                "action": "receive",
                "receive_lines": [
                    {
                        "line_id": "33333333-3333-3333-3333-333333333333",
                        "qty": 1,
                        "location_code": "ONLINE-A1",
                        "pool": "VENTA",
                        "location_is_vendible": True,
                    }
                ],
            }
        }
    }


class TransferReportShortagesActionRequest(BaseModel):
    transaction_id: str | None
    tenant_id: str | None = Field(default=None, json_schema_extra={"deprecated": True})
    action: Literal["report_shortages"]
    shortages: list[TransferShortageLine] | None = None

    model_config = {"extra": "forbid"}


class TransferResolveShortagesActionRequest(BaseModel):
    transaction_id: str | None
    tenant_id: str | None = Field(default=None, json_schema_extra={"deprecated": True})
    action: Literal["resolve_shortages"]
    resolution: TransferShortageResolution | None = None

    model_config = {"extra": "forbid"}


TransferActionRequest = Annotated[
    TransferDispatchActionRequest
    | TransferCancelActionRequest
    | TransferReceiveActionRequest
    | TransferReportShortagesActionRequest
    | TransferResolveShortagesActionRequest,
    Field(discriminator="action"),
]


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

    model_config = {
        "json_schema_extra": {
            "example": {
                "header": {
                    "id": "aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb",
                    "tenant_id": "aaaaaaaa-0000-0000-0000-cccccccccccc",
                    "origin_store_id": "11111111-1111-1111-1111-111111111111",
                    "destination_store_id": "22222222-2222-2222-2222-222222222222",
                    "status": "DRAFT",
                    "created_by_user_id": "dddddddd-1111-2222-3333-eeeeeeeeeeee",
                    "updated_by_user_id": "dddddddd-1111-2222-3333-eeeeeeeeeeee",
                    "dispatched_by_user_id": None,
                    "canceled_by_user_id": None,
                    "dispatched_at": None,
                    "canceled_at": None,
                    "received_at": None,
                    "created_at": "2026-03-27T10:00:00Z",
                    "updated_at": "2026-03-27T10:00:00Z",
                },
                "lines": [
                    {
                        "id": "33333333-3333-3333-3333-333333333333",
                        "line_type": "EPC",
                        "qty": 1,
                        "received_qty": 0,
                        "outstanding_qty": 1,
                        "shortage_status": "NONE",
                        "resolution_status": "NONE",
                        "snapshot": _TRANSFER_LINE_SNAPSHOT_EXAMPLE,
                        "created_at": "2026-03-27T10:00:00Z",
                    }
                ],
                "movement_summary": {
                    "dispatched_lines": 0,
                    "dispatched_qty": 0,
                    "pending_reception": False,
                    "shortages_possible": False,
                },
            }
        }
    }


class TransferListResponse(BaseModel):
    rows: list[TransferResponse]
    meta: "TransferListMeta | None" = None


class TransferListMeta(BaseModel):
    page: int
    page_size: int
    total: int


class TransferStoreResponse(BaseModel):
    id: str
    code: str | None = None
    name: str
    active: bool | None = None


class TransferStoreListResponse(BaseModel):
    rows: list[TransferStoreResponse]
