from __future__ import annotations

import requests
import responses

from aris3_client_sdk import load_config
from aris3_client_sdk.clients.pos_sales_client import PosSalesClient
from aris3_client_sdk.clients.stock_client import StockClient
from aris3_client_sdk.exceptions import ConflictError, ForbiddenError, TransportError
from aris3_client_sdk.stock_validation import ClientValidationError
from aris3_client_sdk.http_client import HttpClient
from aris3_client_sdk.models_stock import StockQuery
from aris3_client_sdk.tracing import TraceContext


def _http(base_url: str) -> HttpClient:
    cfg = load_config()
    object.__setattr__(cfg, "api_base_url", base_url)
    return HttpClient(cfg, trace=TraceContext())


@responses.activate
def test_permission_denied_per_module_paths(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _http("https://api.example.com")

    responses.add(
        responses.GET,
        "https://api.example.com/aris3/stock",
        json={"code": "PERMISSION_DENIED", "message": "no stock", "details": None, "trace_id": "trace-stock"},
        status=403,
    )
    responses.add(
        responses.GET,
        "https://api.example.com/aris3/pos/sales",
        json={"code": "PERMISSION_DENIED", "message": "no pos", "details": None, "trace_id": "trace-pos"},
        status=403,
    )

    stock = StockClient(http=http, access_token="token")
    pos = PosSalesClient(http=http, access_token="token")

    try:
        stock.get_stock(StockQuery())
    except ForbiddenError as exc:
        assert exc.trace_id == "trace-stock"
    else:
        raise AssertionError("Expected forbidden stock path")

    try:
        pos.list_sales()
    except ForbiddenError as exc:
        assert exc.trace_id == "trace-pos"
    else:
        raise AssertionError("Expected forbidden pos path")


@responses.activate
def test_error_mapping_network_validation_and_conflict(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _http("https://api.example.com")
    stock = StockClient(http=http, access_token="token")

    try:
        stock.import_epc([])
    except ClientValidationError as exc:
        assert "lines" in str(exc)
    else:
        raise AssertionError("Expected validation error")

    original = http.session.request

    def _raise(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise requests.ConnectionError("downstream unavailable")

    http.session.request = _raise  # type: ignore[assignment]
    try:
        stock.get_stock(StockQuery())
    except TransportError as exc:
        assert exc.status_code == 0
        assert exc.code == "TRANSPORT_ERROR"
    else:
        raise AssertionError("Expected transport error")
    finally:
        http.session.request = original  # type: ignore[assignment]

    responses.add(
        responses.POST,
        "https://api.example.com/aris3/pos/sales/sale-1/actions",
        json={"code": "CONFLICT", "message": "sale already finalized", "details": None, "trace_id": "trace-conflict"},
        status=409,
    )

    pos = PosSalesClient(http=http, access_token="token")
    try:
        pos.sale_action(
            "sale-1",
            "checkout",
            {"action": "checkout", "transaction_id": "txn-c-1", "payments": [{"method": "CARD", "amount": 10}]},
            idempotency_key="idem-c-1",
        )
    except ConflictError as exc:
        assert exc.trace_id == "trace-conflict"
    else:
        raise AssertionError("Expected conflict path")

    assert responses.calls[0].request.headers["Idempotency-Key"] == "idem-c-1"
