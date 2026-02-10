from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class CountState(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"
    RECONCILED = "RECONCILED"


class CountScope(BaseModel):
    model_config = ConfigDict(extra="allow")

    store_id: str
    zone: str | None = None
    pool: str | None = None


class CountHeader(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    tenant_id: str | None = None
    store_id: str
    state: str
    scope: CountScope | None = None
    lock_active: bool | None = None
    started_at: datetime | None = None
    paused_at: datetime | None = None
    closed_at: datetime | None = None
    reconciled_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CountQuery(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    store_id: str | None = None
    state: str | None = None
    q: str | None = None
    from_date: datetime | str | None = Field(default=None, alias="from")
    to_date: datetime | str | None = Field(default=None, alias="to")
    page: int | None = None
    page_size: int | None = None


class CountRow(BaseModel):
    model_config = ConfigDict(extra="allow")

    header: CountHeader


class CountListResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    rows: list[CountRow]


class CountCreateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    transaction_id: str | None = None
    store_id: str
    scope: CountScope | None = None
    note: str | None = None


class CountActionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    transaction_id: str | None = None
    action: str
    note: str | None = None
    reason_code: str | None = None


class ScanItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    epc: str | None = None
    sku: str | None = None
    qty: int = 1
    location_code: str | None = None
    pool: str | None = None


class ScanBatchRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    transaction_id: str | None = None
    items: list[ScanItem]


class ScanMutationLineResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    row_index: int | None = None
    status: str | None = None
    code: str | None = None
    message: str | None = None


class ScanBatchResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    count_id: str
    accepted: int
    rejected: int
    line_results: list[ScanMutationLineResult] = []


class CountSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    count_id: str
    expected_units: int | None = None
    counted_units: int | None = None
    variance_units: int | None = None


class CountDifferenceLine(BaseModel):
    model_config = ConfigDict(extra="allow")

    sku: str | None = None
    epc: str | None = None
    expected_qty: int | None = None
    counted_qty: int | None = None
    delta_qty: int | None = None


class CountDifferencesResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    count_id: str
    rows: list[CountDifferenceLine]


class ReconcileRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    transaction_id: str | None = None
    action: str = "RECONCILE"
    note: str | None = None


class ReconcileResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    count_id: str
    state: str
    reconciled_at: datetime | None = None


class CountExportResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    count_id: str
    format: str
    url: str | None = None
    file_name: str | None = None
