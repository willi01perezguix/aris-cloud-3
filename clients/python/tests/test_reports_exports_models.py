from __future__ import annotations

from aris3_client_sdk.models_exports import ExportStatus
from aris3_client_sdk.models_reports import ReportDailyResponse, ReportFilter


def test_report_filter_serialization_aliases() -> None:
    filt = ReportFilter(store_id="store-1", from_value="2024-01-01", to_value="2024-01-07", timezone="UTC")
    data = filt.model_dump(by_alias=True, exclude_none=True, mode="json")
    assert data["from"] == "2024-01-01"
    assert data["to"] == "2024-01-07"


def test_report_model_parsing_optional_fields() -> None:
    parsed = ReportDailyResponse.model_validate(
        {
            "meta": {
                "store_id": "store-1",
                "timezone": "UTC",
                "from_datetime": "2024-01-01T00:00:00Z",
                "to_datetime": "2024-01-01T23:59:59Z",
                "trace_id": "t1",
                "filters": {},
            },
            "totals": {
                "gross_sales": "0",
                "refunds_total": "0",
                "net_sales": "0",
                "cogs_gross": "0",
                "cogs_reversed_from_returns": "0",
                "net_cogs": "0",
                "net_profit": "0",
                "orders_paid_count": 0,
                "average_ticket": "0",
            },
            "rows": [],
            "new_field": "future",
        }
    )
    assert parsed.meta.query_ms is None


def test_export_status_model_and_artifact() -> None:
    parsed = ExportStatus.model_validate(
        {
            "export_id": "exp-1",
            "tenant_id": "tenant-1",
            "store_id": "store-1",
            "source_type": "reports_daily",
            "format": "csv",
            "filters_snapshot": {},
            "status": "READY",
            "row_count": 1,
            "checksum_sha256": "abc",
            "failure_reason_code": None,
            "generated_by_user_id": "u1",
            "generated_at": None,
            "trace_id": "t1",
            "file_size_bytes": 1,
            "content_type": "text/csv",
            "file_name": "x.csv",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": None,
        }
    )
    artifact = parsed.artifact(api_base_url="https://api.example.com")
    assert artifact.url == "https://api.example.com/aris3/exports/exp-1/download"
