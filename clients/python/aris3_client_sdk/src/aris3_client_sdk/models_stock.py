from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StockQuery(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    q: str | None = None
    description: str | None = None
    var1_value: str | None = None
    var2_value: str | None = None
    sku: str | None = None
    epc: str | None = None
    location_code: str | None = None
    pool: str | None = None
    from_date: datetime | str | None = Field(default=None, alias="from")
    to_date: datetime | str | None = Field(default=None, alias="to")
    page: int | None = None
    page_size: int | None = None
    sort_by: str | None = None
    sort_order: str | None = Field(default=None, alias="sort_dir")


class StockMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    page: int | None = None
    page_size: int | None = None
    sort_by: str | None = None
    sort_dir: str | None = None


class StockRow(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    tenant_id: str | None = None
    sku: str | None = None
    description: str | None = None
    var1_value: str | None = None
    var2_value: str | None = None
    epc: str | None = None
    location_code: str | None = None
    pool: str | None = None
    status: str | None = None
    location_is_vendible: bool | None = None
    image_asset_id: str | None = None
    image_url: str | None = None
    image_thumb_url: str | None = None
    image_source: str | None = None
    image_updated_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class StockTotals(BaseModel):
    model_config = ConfigDict(extra="allow")

    total_rows: int | None = None
    total_rfid: int | None = None
    total_pending: int | None = None
    total_units: int | None = None


class StockTableResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    meta: StockMeta
    rows: list[StockRow]
    totals: StockTotals


class StockDataBlock(BaseModel):
    model_config = ConfigDict(extra="allow")

    sku: str | None = None
    description: str | None = None
    var1_value: str | None = None
    var2_value: str | None = None
    epc: str | None = None
    location_code: str | None = None
    pool: str | None = None
    status: str | None = None
    location_is_vendible: bool | None = None
    image_asset_id: str | None = None
    image_url: str | None = None
    image_thumb_url: str | None = None
    image_source: str | None = None
    image_updated_at: datetime | None = None


class StockImportEpcLine(StockDataBlock):
    qty: int


class StockImportSkuLine(StockDataBlock):
    qty: int


class StockImportEpcRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    transaction_id: str | None = None
    tenant_id: str | None = None
    lines: list[StockImportEpcLine]


class StockImportSkuRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    transaction_id: str | None = None
    tenant_id: str | None = None
    lines: list[StockImportSkuLine]


class StockMutationLineResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    row_index: int | None = None
    status: str | None = None
    code: str | None = None
    message: str | None = None
    field: str | None = None
    details: dict | None = None


class StockImportResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    tenant_id: str | None = None
    processed: int | None = None
    trace_id: str | None = None
    line_results: list[StockMutationLineResult] | None = None


class StockMigrateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    transaction_id: str | None = None
    tenant_id: str | None = None
    epc: str
    data: StockDataBlock


class StockMigrateResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    tenant_id: str | None = None
    migrated: int | None = None
    trace_id: str | None = None
    line_results: list[StockMutationLineResult] | None = None
