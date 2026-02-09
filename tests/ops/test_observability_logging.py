from types import SimpleNamespace

from starlette.requests import Request
from starlette.responses import Response

from app.aris3.middleware.observability import build_request_log_payload


def test_build_request_log_payload():
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/aris3/stock",
        "headers": [],
        "route": SimpleNamespace(path="/aris3/stock"),
    }
    request = Request(scope)
    request.state.trace_id = "trace-1"
    request.state.tenant_id = "tenant-1"
    request.state.user_id = "user-1"
    request.state.error_code = None
    response = Response(status_code=200)

    payload = build_request_log_payload(
        request=request,
        response=response,
        latency_ms=12.3456,
        db_time_ms=4.5678,
    )

    assert payload["trace_id"] == "trace-1"
    assert payload["tenant_id"] == "tenant-1"
    assert payload["user_id"] == "user-1"
    assert payload["route"] == "/aris3/stock"
    assert payload["method"] == "GET"
    assert payload["status_code"] == 200
    assert payload["latency_ms"] == 12.35
    assert payload["db_time_ms"] == 4.57
