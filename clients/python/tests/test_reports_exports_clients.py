from __future__ import annotations

import responses

from aris3_client_sdk import load_config
from aris3_client_sdk.clients.exports_client import ExportsClient
from aris3_client_sdk.clients.reports_client import ReportsClient
from aris3_client_sdk.exceptions import ForbiddenError, ValidationError
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
def test_report_daily_and_calendar_success(monkeypatch) -> None:
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
        "rows": [
            {
                "business_date": "2024-01-01",
                "gross_sales": "10.00",
                "refunds_total": "0.00",
                "net_sales": "10.00",
                "cogs_gross": "0.00",
                "cogs_reversed_from_returns": "0.00",
                "net_cogs": "0.00",
                "net_profit": "10.00",
                "orders_paid_count": 1,
                "average_ticket": "10.00",
            }
        ],
    }
    responses.add(responses.GET, "https://api.example.com/aris3/reports/daily", json=payload, status=200)
    responses.add(
        responses.GET,
        "https://api.example.com/aris3/reports/calendar",
        json={**payload, "rows": [{"business_date": "2024-01-01", "net_sales": "10.00", "net_profit": "10.00", "orders_paid_count": 1}]},
        status=200,
    )
    client = ReportsClient(http=http, access_token="token")
    assert len(client.get_sales_daily().rows) == 1
    assert len(client.get_sales_calendar().rows) == 1


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
    try:
        client.get_sales_daily()
    except ForbiddenError as exc:
        assert exc.code == "REPORT_SCOPE_FORBIDDEN"
        assert exc.trace_id == "t-1"
    else:
        raise AssertionError("Expected forbidden")


@responses.activate
def test_export_request_and_polling(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    created = {
        "export_id": "exp-1",
        "tenant_id": "tenant-1",
        "store_id": "store-1",
        "source_type": "reports_daily",
        "format": "csv",
        "filters_snapshot": {},
        "status": "CREATED",
        "row_count": 0,
        "checksum_sha256": None,
        "failure_reason_code": None,
        "generated_by_user_id": "u1",
        "generated_at": None,
        "trace_id": "trace-1",
        "file_size_bytes": None,
        "content_type": None,
        "file_name": None,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": None,
    }
    ready = {**created, "status": "READY", "file_name": "report.csv", "content_type": "text/csv", "file_size_bytes": 12, "checksum_sha256": "abc"}
    responses.add(responses.POST, "https://api.example.com/aris3/exports", json=created, status=201)
    responses.add(responses.GET, "https://api.example.com/aris3/exports/exp-1", json=created, status=200)
    responses.add(responses.GET, "https://api.example.com/aris3/exports/exp-1", json=ready, status=200)
    client = ExportsClient(http=http, access_token="token")
    req = ExportRequest(source_type="reports_daily", format="csv", filters=ReportFilter(store_id="store-1"), transaction_id="txn-1")
    status = client.request_export(req, idempotency_key="idem-1")
    assert status.export_id == "exp-1"
    final = client.wait_until_ready("exp-1", timeout_seconds=1.5, poll_interval_seconds=0.01)
    assert final.status == "READY"


@responses.activate
def test_report_validation_trace_id_preserved(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    responses.add(
        responses.GET,
        "https://api.example.com/aris3/reports/overview",
        json={"code": "VALIDATION_ERROR", "message": "bad dates", "details": {}, "trace_id": "trace-bad"},
        status=400,
    )
    client = ReportsClient(http=http, access_token="token")
    try:
        client.get_sales_overview({"from": "x", "to": "y"})
    except ValidationError as exc:
        assert exc.code == "REPORT_INVALID_DATE_RANGE"
        assert exc.trace_id == "trace-bad"
    else:
        raise AssertionError("expected validation")
