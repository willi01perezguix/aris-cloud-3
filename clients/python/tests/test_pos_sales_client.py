from __future__ import annotations

import json

import responses

from aris3_client_sdk import load_config
from aris3_client_sdk.clients.pos_sales_client import PosSalesClient
from aris3_client_sdk.exceptions import ForbiddenError, UnauthorizedError
from aris3_client_sdk.http_client import HttpClient
from aris3_client_sdk.tracing import TraceContext


def _client(base_url: str) -> HttpClient:
    cfg = load_config()
    object.__setattr__(cfg, "api_base_url", base_url)
    return HttpClient(cfg, trace=TraceContext())


def _sale_response(sale_id: str, status: str = "DRAFT") -> dict:
    return {
        "header": {
            "id": sale_id,
            "tenant_id": "tenant-1",
            "store_id": "store-1",
            "status": status,
            "total_due": 10.0,
            "paid_total": 0.0,
            "balance_due": 10.0,
            "change_due": 0.0,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": None,
        },
        "lines": [],
        "payments": [],
        "payment_summary": [],
        "refunded_totals": {"subtotal": 0, "restocking_fee": 0, "total": 0},
        "exchanged_totals": {"subtotal": 0, "restocking_fee": 0, "total": 0},
        "net_adjustment": 0,
        "return_events": [],
    }


@responses.activate
def test_create_sale_success(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    responses.add(
        responses.POST,
        "https://api.example.com/aris3/pos/sales",
        json=_sale_response("sale-1"),
        status=201,
    )
    client = PosSalesClient(http=http, access_token="token")
    response = client.create_sale(
        {
            "transaction_id": "txn-1",
            "store_id": "store-1",
            "lines": [
                {
                    "line_type": "SKU",
                    "qty": 1,
                    "unit_price": 10.0,
                    "snapshot": {"sku": "SKU-1", "location_code": "LOC-1", "pool": "P1"},
                }
            ],
        },
        idempotency_key="idem-1",
    )
    assert response.header.id == "sale-1"
    assert responses.calls[0].request.headers["Idempotency-Key"] == "idem-1"


@responses.activate
def test_update_sale_payloads(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    responses.add(
        responses.PATCH,
        "https://api.example.com/aris3/pos/sales/sale-1",
        json=_sale_response("sale-1"),
        status=200,
    )
    client = PosSalesClient(http=http, access_token="token")
    client.update_sale(
        "sale-1",
        {
            "transaction_id": "txn-2",
            "lines": [
                {
                    "line_type": "EPC",
                    "qty": 1,
                    "unit_price": 5.0,
                    "snapshot": {"epc": "EPC-1", "location_code": "LOC-1", "pool": "P1"},
                },
                {
                    "line_type": "SKU",
                    "qty": 2,
                    "unit_price": 5.0,
                    "snapshot": {"sku": "SKU-2", "location_code": "LOC-1", "pool": "P1"},
                },
            ],
        },
        idempotency_key="idem-2",
    )
    body = json.loads(responses.calls[0].request.body.decode("utf-8"))
    assert body["lines"][0]["line_type"] == "EPC"
    assert body["lines"][1]["line_type"] == "SKU"


@responses.activate
def test_checkout_action_includes_idempotency(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    responses.add(
        responses.POST,
        "https://api.example.com/aris3/pos/sales/sale-1/actions",
        json=_sale_response("sale-1", status="PAID"),
        status=200,
    )
    client = PosSalesClient(http=http, access_token="token")
    response = client.sale_action(
        "sale-1",
        "checkout",
        {"transaction_id": "txn-3", "action": "checkout", "payments": [{"method": "CASH", "amount": 10.0}]},
        idempotency_key="idem-3",
    )
    assert response.header.status == "PAID"
    assert responses.calls[0].request.headers["Idempotency-Key"] == "idem-3"


@responses.activate
def test_pos_sale_unauthorized_forbidden(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    responses.add(
        responses.GET,
        "https://api.example.com/aris3/pos/sales/sale-1",
        json={"code": "INVALID_TOKEN", "message": "no", "details": None, "trace_id": "trace"},
        status=401,
    )
    responses.add(
        responses.GET,
        "https://api.example.com/aris3/pos/sales",
        json={"code": "PERMISSION_DENIED", "message": "no", "details": None, "trace_id": "trace"},
        status=403,
    )
    client = PosSalesClient(http=http, access_token="token")
    try:
        client.get_sale("sale-1")
    except UnauthorizedError:
        pass
    else:
        raise AssertionError("Expected UnauthorizedError")
    try:
        client.list_sales()
    except ForbiddenError:
        pass
    else:
        raise AssertionError("Expected ForbiddenError")
