from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ExportSourceType(str, Enum):
    REPORTS_OVERVIEW = "reports_overview"
    REPORTS_DAILY = "reports_daily"
    REPORTS_CALENDAR = "reports_calendar"


class ExportFormat(str, Enum):
    CSV = "csv"
    XLSX = "xlsx"
    PDF = "pdf"


class ExportStatus(str, Enum):
    CREATED = "CREATED"
    READY = "READY"
    FAILED = "FAILED"


class ExportFilters(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    store_id: str | None = None
    from_value: str | None = Field(None, alias="from", description="ISO 8601/date, inclusive start")
    to_value: str | None = Field(None, alias="to", description="ISO 8601/date, inclusive end")
    timezone: str | None = Field(None, description="Timezone used to resolve date boundaries. Defaults to UTC when omitted.")
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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "source_type": "reports_overview",
                "format": "csv",
                "filters": {
                    "store_id": "f35a8cb4-3f99-4fca-aaf0-3b2ca1801111",
                    "from": "2026-03-01T00:00:00-06:00",
                    "to": "2026-03-01T23:59:59.999999-06:00",
                    "timezone": "America/Mexico_City",
                },
                "file_name": "overview_report_20260301.csv",
                "transaction_id": "txn-export-001",
            }
        }
    )


class ExportResponse(BaseModel):
    export_id: str
    tenant_id: str
    store_id: str
    source_type: ExportSourceType
    format: ExportFormat
    filters_snapshot: ExportFilters
    status: ExportStatus
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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "export_id": "d8cdf2b6-3ccf-49da-b2d6-c1ff39f2c9d5",
                "tenant_id": "d5f18db6-7e1f-4cb4-a793-a5f6f7227a01",
                "store_id": "f35a8cb4-3f99-4fca-aaf0-3b2ca1801111",
                "source_type": "reports_overview",
                "format": "csv",
                "filters_snapshot": {
                    "store_id": "f35a8cb4-3f99-4fca-aaf0-3b2ca1801111",
                    "from": "2026-03-01T00:00:00-06:00",
                    "to": "2026-03-01T23:59:59.999999-06:00",
                    "timezone": "America/Mexico_City",
                },
                "status": "READY",
                "row_count": 1,
                "checksum_sha256": "7f83b1657ff1fc53b92dc18148a1d65dfa13514a5c4f1be6be5f5f6f6f6f6f6f",
                "failure_reason_code": None,
                "generated_by_user_id": "81b4153e-90f3-4a8a-8f79-1d5903622222",
                "generated_at": "2026-03-01T12:02:03Z",
                "trace_id": "trace-export-001",
                "file_size_bytes": 510,
                "content_type": "text/csv",
                "file_name": "overview_report_20260301.csv",
                "created_at": "2026-03-01T12:02:01Z",
                "updated_at": "2026-03-01T12:02:03Z",
            }
        },
        use_enum_values=True,
    )


ExportStatus.__doc__ = (
    "Export lifecycle states used by ARIS3 exports: "
    "`CREATED` (accepted and pending generation), `READY` (file generated and downloadable), "
    "`FAILED` (generation failed and requires a new export request)."
    )


class ExportListResponse(BaseModel):
    rows: list[ExportResponse]
