from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field
from pydantic import ConfigDict


ExportSourceType = Literal["reports_overview", "reports_daily", "reports_calendar"]
ExportFormat = Literal["csv", "xlsx", "pdf"]


class ExportFilters(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    store_id: str | None = None
    from_value: str | None = Field(None, alias="from")
    to_value: str | None = Field(None, alias="to")
    timezone: str | None = None
    cashier: str | None = None
    channel: str | None = None
    payment_method: str | None = None

    def snapshot(self) -> dict:
        return {
            "store_id": self.store_id,
            "from": self.from_value,
            "to": self.to_value,
            "timezone": self.timezone,
            "cashier": self.cashier,
            "channel": self.channel,
            "payment_method": self.payment_method,
        }


class ExportCreateRequest(BaseModel):
    source_type: ExportSourceType
    format: ExportFormat
    filters: ExportFilters
    file_name: str | None = None
    transaction_id: str


class ExportResponse(BaseModel):
    export_id: str
    tenant_id: str
    store_id: str
    source_type: ExportSourceType
    format: ExportFormat
    filters_snapshot: dict
    status: str
    row_count: int
    checksum_sha256: str | None
    generated_by_user_id: str | None
    generated_at: datetime | None
    trace_id: str | None
    file_size_bytes: int | None
    content_type: str | None
    file_name: str | None
    created_at: datetime
    updated_at: datetime | None


class ExportListResponse(BaseModel):
    rows: list[ExportResponse]
