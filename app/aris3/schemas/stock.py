from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, PlainSerializer, WithJsonSchema


MoneyValue = Annotated[
    Decimal,
    Field(ge=0, max_digits=12, decimal_places=2),
    PlainSerializer(lambda value: format(value.quantize(Decimal("0.01")), "f"), return_type=str, when_used="json"),
    WithJsonSchema(
        {
            "anyOf": [
                {"type": "number", "minimum": 0},
                {"type": "string", "pattern": r"^\d{1,10}(?:\.\d{1,2})?$"},
            ]
        },
        mode="validation",
    ),
    WithJsonSchema({"type": "string", "pattern": r"^\d{1,10}(?:\.\d{2})?$"}, mode="serialization"),
]


_MONEY_FIELD_DESCRIPTION = "Acepta number o string decimal en request; se serializa como string decimal en responses"


class StockRow(BaseModel):
    sku: str | None
    description: str | None
    var1_value: str | None
    var2_value: str | None
    cost_price: MoneyValue | None = Field(default=None, examples=["25.00"], description=_MONEY_FIELD_DESCRIPTION)
    suggested_price: MoneyValue | None = Field(default=None, examples=["35.00"], description=_MONEY_FIELD_DESCRIPTION)
    sale_price: MoneyValue | None = Field(default=None, examples=["32.50"], description=_MONEY_FIELD_DESCRIPTION)
    epc: str | None
    location_code: str | None
    pool: str | None
    status: str | None
    location_is_vendible: bool
    image_asset_id: str | None
    image_url: str | None
    image_thumb_url: str | None
    image_source: str | None
    image_updated_at: datetime | None
    id: str
    tenant_id: str
    created_at: datetime
    updated_at: datetime | None

    model_config = {
        "json_schema_extra": {
            "example": {
                "sku": "SKU-1",
                "description": "Blue Jacket",
                "var1_value": "Blue",
                "var2_value": "L",
                "cost_price": "25.00",
                "suggested_price": "35.00",
                "sale_price": "32.50",
                "epc": "ABCDEFABCDEFABCDEFABCDEF",
                "location_code": "LOC-1",
                "pool": "P1",
                "status": "RFID",
                "location_is_vendible": True,
                "image_asset_id": "7fa2f29e-3ffd-4e52-a0a5-8f53d0ae1a61",
                "image_url": "https://example.com/image.png",
                "image_thumb_url": "https://example.com/thumb.png",
                "image_source": "catalog",
                "image_updated_at": "2025-01-01T00:00:00Z",
                "id": "fef5d8de-0f6f-4a64-b6ce-8fcdb4128ffb",
                "tenant_id": "eec4e17f-d5f0-489f-a1c1-7f6ad5039f22",
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:05:00Z",
            }
        }
    }


class StockQueryMeta(BaseModel):
    page: int
    page_size: int
    sort_by: str
    sort_dir: Literal["asc", "desc"]


class StockQueryTotals(BaseModel):
    total_rows: int
    total_rfid: int
    total_pending: int
    total_units: int


class StockQueryResponse(BaseModel):
    meta: StockQueryMeta
    rows: list[StockRow]
    totals: StockQueryTotals


class StockDataBlock(BaseModel):
    sku: str | None
    description: str | None
    var1_value: str | None
    var2_value: str | None
    cost_price: MoneyValue | None = Field(default=None, examples=["25.00"], description=_MONEY_FIELD_DESCRIPTION)
    suggested_price: MoneyValue | None = Field(default=None, examples=["35.00"], description=_MONEY_FIELD_DESCRIPTION)
    sale_price: MoneyValue | None = Field(default=None, examples=["32.50"], description=_MONEY_FIELD_DESCRIPTION)
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

    model_config = {
        "json_schema_extra": {
            "example": {
                "sku": "SKU-1",
                "description": "Blue Jacket",
                "var1_value": "Blue",
                "var2_value": "L",
                "cost_price": "25.00",
                "suggested_price": "35.00",
                "sale_price": "32.50",
                "epc": "ABCDEFABCDEFABCDEFABCDEF",
                "location_code": "LOC-1",
                "pool": "P1",
                "status": "RFID",
                "location_is_vendible": True,
                "image_asset_id": "7fa2f29e-3ffd-4e52-a0a5-8f53d0ae1a61",
                "image_url": "https://example.com/image.png",
                "image_thumb_url": "https://example.com/thumb.png",
                "image_source": "catalog",
                "image_updated_at": "2025-01-01T00:00:00Z",
            }
        }
    }


class StockImportEpcLine(StockDataBlock):
    qty: int


class StockImportSkuLine(StockDataBlock):
    qty: int


class StockImportEpcRequest(BaseModel):
    transaction_id: str | None
    tenant_id: str | None = None
    lines: list[StockImportEpcLine]


class StockImportSkuRequest(BaseModel):
    transaction_id: str | None
    tenant_id: str | None = None
    lines: list[StockImportSkuLine]


class StockImportResponse(BaseModel):
    tenant_id: str
    processed: int
    trace_id: str


class StockMigrateRequest(BaseModel):
    transaction_id: str | None
    tenant_id: str | None = None
    epc: str
    data: StockDataBlock


class StockMigrateResponse(BaseModel):
    tenant_id: str
    migrated: int
    trace_id: str


class StockActionWriteOffPayload(BaseModel):
    reason: str | None
    qty: int = 1
    data: StockDataBlock


class StockActionRepricePayload(BaseModel):
    data: StockDataBlock
    price: float | None = None
    currency: str | None = None


class StockActionMarkdownPayload(BaseModel):
    data: StockDataBlock
    policy: str | None = None


class StockActionReprintPayload(BaseModel):
    data: StockDataBlock


class StockActionReplaceEpcPayload(BaseModel):
    current_epc: str
    new_epc: str
    reason: str | None = None


class StockActionEpcLifecyclePayload(BaseModel):
    epc: str
    reason: str | None = None
    epc_type: Literal["NON_REUSABLE_LABEL", "REUSABLE_TAG"] | None = None


class StockActionRequest(BaseModel):
    transaction_id: str | None
    tenant_id: str | None = None
    action: Literal[
        "WRITE_OFF",
        "REPRICE",
        "MARKDOWN_BY_AGE",
        "REPRINT_LABEL",
        "REPLACE_EPC",
        "MARK_EPC_DAMAGED",
        "RETIRE_EPC",
        "RETURN_EPC_TO_POOL",
    ]
    payload: dict


class StockActionResponse(BaseModel):
    tenant_id: str
    action: str
    processed: int
    trace_id: str
