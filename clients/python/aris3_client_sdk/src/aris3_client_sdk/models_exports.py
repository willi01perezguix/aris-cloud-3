from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .models_reports import ReportFilter

ExportSourceType = Literal["reports_overview", "reports_daily", "reports_calendar"]
ExportFormat = Literal["csv", "xlsx", "pdf"]


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_type: ExportSourceType
    format: ExportFormat
    filters: ReportFilter
    file_name: str | None = None
    transaction_id: str


class ExportArtifact(BaseModel):
    model_config = ConfigDict(extra="allow")

    export_id: str
    file_name: str | None = None
    url: str | None = None
    content_type: str | None = None
    file_size_bytes: int | None = None
    checksum_sha256: str | None = None


class ExportStatus(BaseModel):
    model_config = ConfigDict(extra="allow")

    export_id: str
    tenant_id: str
    store_id: str
    source_type: ExportSourceType
    format: ExportFormat
    filters_snapshot: dict[str, object]
    status: str
    row_count: int
    checksum_sha256: str | None = None
    failure_reason_code: str | None = None
    generated_by_user_id: str | None = None
    generated_at: datetime | None = None
    trace_id: str | None = None
    file_size_bytes: int | None = None
    content_type: str | None = None
    file_name: str | None = None
    created_at: datetime
    updated_at: datetime | None = None

    def artifact(self, api_base_url: str | None = None) -> ExportArtifact:
        download_url = None
        if api_base_url and self.status.upper() == "READY":
            base = api_base_url.rstrip("/")
            download_url = f"{base}/aris3/exports/{self.export_id}/download"
        return ExportArtifact(
            export_id=self.export_id,
            file_name=self.file_name,
            url=download_url,
            content_type=self.content_type,
            file_size_bytes=self.file_size_bytes,
            checksum_sha256=self.checksum_sha256,
        )


class ExportListResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    rows: list[ExportStatus] = Field(default_factory=list)
