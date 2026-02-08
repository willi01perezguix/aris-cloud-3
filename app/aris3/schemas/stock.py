from datetime import datetime
from typing import Literal

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
