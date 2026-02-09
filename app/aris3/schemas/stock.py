from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class StockRow(BaseModel):
    id: str
    tenant_id: str
    sku: str | None
    description: str | None
    var1_value: str | None
    var2_value: str | None
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
    created_at: datetime
    updated_at: datetime | None


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
