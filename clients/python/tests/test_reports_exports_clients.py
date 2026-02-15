from __future__ import annotations

import pytest
import responses

from aris3_client_sdk import load_config
from aris3_client_sdk.clients.exports_client import ExportsClient
from aris3_client_sdk.clients.reports_client import ReportsClient
from aris3_client_sdk.exceptions import ForbiddenError, NotFoundError, UnauthorizedError, ValidationError
from aris3_client_sdk.http_client import HttpClient
from aris3_client_sdk.models_exports import ExportRequest
from aris3_client_sdk.models_reports import ReportFilter
from aris3_client_sdk.tracing import TraceContext


def _client(base_url: str) -> HttpClient:
    cfg = load_config()
    object.__setattr__(cfg, "api_base_url", base_url)
    return HttpClient(cfg, trace=TraceContext())


@responses.activate
def test_report_overview_success(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    responses.add(
        responses.GET,
        "https://api.example.com/aris3/reports/overview",
        json={
            "meta": {
                "store_id": "store-1",
                "timezone": "UTC",
                "from_datetime": "2024-01-01T00:00:00Z",
                "to_datetime": "2024-01-07T23:59:59Z",
                "trace_id": "trace-1",
                "query_ms": 12,
                "filters": {},
            },
            "totals": {
                "gross_sales": "100.00",
                "refunds_total": "5.00",
                "net_sales": "95.00",
                "cogs_gross": "0.00",
                "cogs_reversed_from_returns": "0.00",
                "net_cogs": "0.00",
                "net_profit": "95.00",
                "orders_paid_count": 10,
                "average_ticket": "9.50",
            },
        },
        status=200,
    )
    response = ReportsClient(http=http, access_token="token").get_sales_overview(ReportFilter(store_id="store-1"))
    assert str(response.totals.net_sales) == "95.00"


@responses.activate
def test_report_daily_advanced_filters_serialized(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    payload = {
        "meta": {
            "store_id": "store-1",
            "timezone": "UTC",
            "from_datetime": "2024-01-01T00:00:00Z",
            "to_datetime": "2024-01-01T23:59:59Z",
            "trace_id": "trace-1",
            "query_ms": 8,
            "filters": {},
        },
        "totals": {
            "gross_sales": "10.00",
            "refunds_total": "0.00",
            "net_sales": "10.00",
            "cogs_gross": "0.00",
            "cogs_reversed_from_returns": "0.00",
            "net_cogs": "0.00",
            "net_profit": "10.00",
            "orders_paid_count": 1,
            "average_ticket": "10.00",
        },
        "rows": [{"business_date": "2024-01-01", "gross_sales": "10.00", "refunds_total": "0.00", "net_sales": "10.00", "cogs_gross": "0.00", "cogs_reversed_from_returns": "0.00", "net_cogs": "0.00", "net_profit": "10.00", "orders_paid_count": 1, "average_ticket": "10.00"}],
    }
    responses.add(responses.GET, "https://api.example.com/aris3/reports/daily", json=payload, status=200)
    client = ReportsClient(http=http, access_token="token")
    assert len(client.get_sales_daily({"store_ids": ["store-1"], "date_from": "2024-01-01", "date_to": "2024-01-01", "granularity": "daily"}).rows) == 1


@responses.activate
def test_report_forbidden_scope_mapped(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    responses.add(
        responses.GET,
        "https://api.example.com/aris3/reports/daily",
        json={"code": "STORE_SCOPE_MISMATCH", "message": "bad", "details": {}, "trace_id": "t-1"},
        status=403,
    )
    client = ReportsClient(http=http, access_token="token")
    with pytest.raises(ForbiddenError) as exc:
        client.get_sales_daily()
    assert exc.value.code == "REPORT_SCOPE_FORBIDDEN"
    assert exc.value.trace_id == "t-1"


@responses.activate
def test_export_request_and_polling(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    created = {
        "export_id": "exp-1", "tenant_id": "tenant-1", "store_id": "store-1", "source_type": "reports_daily", "format": "csv",
        "filters_snapshot": {}, "status": "CREATED", "row_count": 0, "checksum_sha256": None, "failure_reason_code": None,
        "generated_by_user_id": "u1", "generated_at": None, "trace_id": "trace-1", "file_size_bytes": None,
        "content_type": None, "file_name": None, "created_at": "2024-01-01T00:00:00Z", "updated_at": None,
    }
    ready = {**created, "status": "READY", "file_name": "report.csv", "content_type": "text/csv", "file_size_bytes": 12, "checksum_sha256": "abc"}
    responses.add(responses.POST, "https://api.example.com/aris3/exports", json=created, status=201)
    responses.add(responses.GET, "https://api.example.com/aris3/exports/exp-1", json=created, status=200)
    responses.add(responses.GET, "https://api.example.com/aris3/exports/exp-1", json=ready, status=200)
    client = ExportsClient(http=http, access_token="token")
    req = ExportRequest(source_type="reports_daily", format="csv", filters=ReportFilter(store_id="store-1"), transaction_id="txn-1")
    status = client.request_export(req, idempotency_key="idem-1")
    assert status.export_id == "exp-1"
    final = client.wait_for_export_ready("exp-1", timeout_sec=1.5, poll_interval_sec=0.01)
    assert final.outcome.value == "COMPLETED"


@responses.activate
def test_export_polling_bypasses_cache_without_disabling_global_cache(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    created = {
        "export_id": "exp-1", "tenant_id": "tenant-1", "store_id": "store-1", "source_type": "reports_daily", "format": "csv",
        "filters_snapshot": {}, "status": "CREATED", "row_count": 0, "checksum_sha256": None, "failure_reason_code": None,
        "generated_by_user_id": "u1", "generated_at": None, "trace_id": "trace-1", "file_size_bytes": None,
        "content_type": None, "file_name": None, "created_at": "2024-01-01T00:00:00Z", "updated_at": None,
    }
    ready = {**created, "status": "READY", "file_name": "report.csv", "content_type": "text/csv", "file_size_bytes": 12, "checksum_sha256": "abc"}
    responses.add(responses.GET, "https://api.example.com/aris3/exports/exp-1", json=created, status=200)
    responses.add(responses.GET, "https://api.example.com/aris3/exports/exp-1", json=ready, status=200)

    client = ExportsClient(http=http, access_token="token")

    warm_status = client.get_export_status("exp-1")
    assert warm_status.status == "CREATED"

    final = client.wait_for_export_ready("exp-1", timeout_sec=1.0, poll_interval_sec=0.01)
    assert final.outcome.value == "COMPLETED"
    assert final.status.status == "READY"
    assert http.enable_get_cache is True

    cached_status = client.get_export_status("exp-1")
    assert cached_status.status == "CREATED"
    assert len(responses.calls) == 2


@responses.activate
def test_export_polling_preserves_disabled_global_cache_state(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    http.enable_get_cache = False

    created = {
        "export_id": "exp-1", "tenant_id": "tenant-1", "store_id": "store-1", "source_type": "reports_daily", "format": "csv",
        "filters_snapshot": {}, "status": "CREATED", "row_count": 0, "checksum_sha256": None, "failure_reason_code": None,
        "generated_by_user_id": "u1", "generated_at": None, "trace_id": "trace-1", "file_size_bytes": None,
        "content_type": None, "file_name": None, "created_at": "2024-01-01T00:00:00Z", "updated_at": None,
    }
    ready = {**created, "status": "READY", "file_name": "report.csv", "content_type": "text/csv", "file_size_bytes": 12, "checksum_sha256": "abc"}
    responses.add(responses.GET, "https://api.example.com/aris3/exports/exp-1", json=created, status=200)
    responses.add(responses.GET, "https://api.example.com/aris3/exports/exp-1", json=ready, status=200)

    client = ExportsClient(http=http, access_token="token")
    final = client.wait_for_export_ready("exp-1", timeout_sec=1.0, poll_interval_sec=0.01)

    assert final.outcome.value == "COMPLETED"
    assert http.enable_get_cache is False
    assert http._cache == {}


@responses.activate
def test_export_poll_timeout(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    pending = {"export_id": "exp-1", "tenant_id": "tenant-1", "store_id": "store-1", "source_type": "reports_daily", "format": "csv", "filters_snapshot": {}, "status": "CREATED", "row_count": 0, "generated_by_user_id": "u1", "generated_at": None, "trace_id": "trace-1", "created_at": "2024-01-01T00:00:00Z", "updated_at": None}
    responses.add(responses.GET, "https://api.example.com/aris3/exports/exp-1", json=pending, status=200)
    client = ExportsClient(http=http, access_token="token")
    with pytest.raises(TimeoutError):
        client.wait_for_export_ready("exp-1", timeout_sec=0.01, poll_interval_sec=0.01)


@responses.activate
def test_export_poll_failed(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    failed = {"export_id": "exp-1", "tenant_id": "tenant-1", "store_id": "store-1", "source_type": "reports_daily", "format": "csv", "filters_snapshot": {}, "status": "FAILED", "row_count": 0, "failure_reason_code": "EXPORT_FAILED", "generated_by_user_id": "u1", "generated_at": None, "trace_id": "trace-1", "created_at": "2024-01-01T00:00:00Z", "updated_at": None}
    responses.add(responses.GET, "https://api.example.com/aris3/exports/exp-1", json=failed, status=200)
    client = ExportsClient(http=http, access_token="token")
    result = client.wait_for_export_ready("exp-1", timeout_sec=1.0, poll_interval_sec=0.01)
    assert result.outcome.value == "FAILED"


@responses.activate
def test_report_validation_trace_id_preserved(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    responses.add(
        responses.GET,
        "https://api.example.com/aris3/reports/overview",
        json={"code": "VALIDATION_ERROR", "message": "bad dates", "details": {"message": "bad dates"}, "trace_id": "trace-bad"},
        status=400,
    )
    client = ReportsClient(http=http, access_token="token")
    with pytest.raises(ValidationError) as exc:
        client.get_sales_overview({"from": "2024-01-01", "to": "2024-01-01"})
    assert exc.value.code == "REPORT_INVALID_DATE_RANGE"
    assert exc.value.trace_id == "trace-bad"


@responses.activate
def test_forbidden_and_unauthorized_scope(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    responses.add(responses.GET, "https://api.example.com/aris3/reports/daily", json={"code": "UNAUTHORIZED", "message": "no", "details": {}, "trace_id": "u-1"}, status=401)
    responses.add(responses.GET, "https://api.example.com/aris3/exports/exp-404", json={"code": "NOT_FOUND", "message": "no", "details": {}, "trace_id": "n-1"}, status=404)
    reports = ReportsClient(http=http, access_token="token")
    exports = ExportsClient(http=http, access_token="token")
    with pytest.raises(UnauthorizedError):
        reports.get_sales_daily()
    with pytest.raises(NotFoundError):
        exports.get_export_status("exp-404")
