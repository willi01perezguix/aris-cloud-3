from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field
from pydantic import ConfigDict


class ExportSourceType(str, Enum):
    REPORTS_OVERVIEW = "reports_overview"
    REPORTS_DAILY = "reports_daily"
    REPORTS_CALENDAR = "reports_calendar"


class ExportFormat(str, Enum):
    CSV = "csv"
    XLSX = "xlsx"
    PDF = "pdf"


class ExportFilters(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    store_id: str | None = None
    from_value: str | None = Field(None, alias="from", description="ISO 8601 (inclusive)")
    to_value: str | None = Field(None, alias="to", description="ISO 8601 (inclusive)")
    timezone: str | None = None
    cashier: str | None = None
    channel: str | None = None
    payment_method: str | None = None

    def snapshot(self) -> dict:
        snapshot = {
            "store_id": self.store_id,
            "from": self.from_value,
            "to": self.to_value,
            "timezone": self.timezone,
            "cashier": self.cashier,
            "channel": self.channel,
            "payment_method": self.payment_method,
        }
        return {key: value for key, value in snapshot.items() if value not in (None, "", {}, [])}


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
    failure_reason_code: str | None
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
