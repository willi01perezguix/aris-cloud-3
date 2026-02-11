from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

import pytest
import responses

from aris3_client_sdk import load_config
from aris3_client_sdk.clients.access_control import AccessControlClient
from aris3_client_sdk.clients.auth import AuthClient
from aris3_client_sdk.clients.pos_cash_client import PosCashClient
from aris3_client_sdk.clients.pos_sales_client import PosSalesClient
from aris3_client_sdk.clients.stock_client import StockClient
from aris3_client_sdk.exceptions import ForbiddenError
from aris3_client_sdk.http_client import HttpClient
from aris3_client_sdk.models_stock import StockQuery
from aris3_client_sdk.tracing import TraceContext


@dataclass
class RequestAudit:
    rows: list[dict[str, object]] = field(default_factory=list)

    def add(self, module: str, action: str, status_code: int, started: float) -> None:
        self.rows.append(
            {
                "trace_id": "trace-s7d7",
                "module": module,
                "action": action,
                "status_code": status_code,
                "duration_ms": int((time.perf_counter() - started) * 1000),
            }
        )


def _http(base_url: str, audit: RequestAudit) -> HttpClient:
    cfg = load_config()
    object.__setattr__(cfg, "api_base_url", base_url)

    def _before(method: str, url: str, ctx: dict[str, object]) -> None:  # noqa: ARG001
        ctx["_started"] = time.perf_counter()

    def _after(response) -> None:  # type: ignore[no-untyped-def]
        started = getattr(response.request, "_started", None)
        if started is None:
            started = time.perf_counter()
        path = response.request.path_url
        if "/stock" in path:
            module = "stock"
        elif "/pos/" in path:
            module = "pos"
        elif "/access-control" in path:
            module = "access"
        else:
            module = "auth"
        audit.add(module, f"{response.request.method} {path}", response.status_code, started)

    client = HttpClient(cfg, trace=TraceContext(), before_request=_before, after_response=_after)
    return client


@responses.activate
def test_cross_module_happy_path_and_denied_flows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    audit = RequestAudit()
    http = _http("https://api.example.com", audit)

    responses.add(
        responses.POST,
        "https://api.example.com/aris3/auth/login",
        json={"access_token": "token", "must_change_password": False, "trace_id": "trace-s7d7"},
        status=200,
    )
    responses.add(
        responses.GET,
        "https://api.example.com/aris3/me",
        json={
            "id": "u1",
            "username": "alpha",
            "email": "alpha@example.com",
            "tenant_id": "t1",
            "store_id": "s1",
            "role": "ADMIN",
            "status": "ACTIVE",
            "is_active": True,
            "must_change_password": False,
            "trace_id": "trace-s7d7",
        },
        status=200,
    )
    responses.add(
        responses.GET,
        "https://api.example.com/aris3/access-control/effective-permissions",
        json={
            "user_id": "u1",
            "tenant_id": "t1",
            "store_id": "s1",
            "role": "ADMIN",
            "permissions": [
                {"key": "stock.view", "allowed": True, "source": "template"},
                {"key": "pos.sale.checkout", "allowed": True, "source": "template"},
            ],
            "subject": {"user_id": "u1", "tenant_id": "t1", "store_id": "s1", "role": "ADMIN"},
            "denies_applied": [],
            "sources_trace": {
                "template": {"allow": ["stock.view"], "deny": []},
                "tenant": {"allow": [], "deny": []},
                "store": {"allow": [], "deny": []},
                "user": {"allow": [], "deny": []},
            },
            "trace_id": "trace-s7d7",
        },
        status=200,
    )
    responses.add(
        responses.GET,
        "https://api.example.com/aris3/stock",
        json={
            "meta": {"page": 1, "page_size": 50, "sort_by": "sku", "sort_dir": "asc"},
            "rows": [
                {
                    "sku": "SKU-1",
                    "description": "Alpha",
                    "var1_value": "BLUE",
                    "var2_value": "42",
                    "epc": "ABCDEFABCDEFABCDEFABCDEF",
                    "location_code": "SELL-1",
                    "pool": "RFID",
                    "status": "RFID",
                }
            ],
            "totals": {"total_rfid": 2, "total_pending": 1, "total_units": 3, "total_rows": 1},
            "trace_id": "trace-s7d7",
        },
        status=200,
    )
    responses.add(
        responses.POST,
        "https://api.example.com/aris3/stock/import-epc",
        json={"processed": 1, "trace_id": "trace-s7d7"},
        status=200,
    )
    responses.add(
        responses.POST,
        "https://api.example.com/aris3/pos/cash/session/actions",
        json={"session_id": "cash-1", "store_id": "s1", "status": "OPEN", "opened_by": "u1", "opening_float": 100, "trace_id": "trace-s7d7"},
        status=201,
    )
    responses.add(
        responses.POST,
        "https://api.example.com/aris3/pos/sales",
        json={
            "header": {
                "id": "sale-1",
                "tenant_id": "t1",
                "store_id": "s1",
                "status": "DRAFT",
                "total_due": 10,
                "paid_total": 0,
                "balance_due": 10,
                "change_due": 0,
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
        },
        status=201,
    )
    responses.add(
        responses.POST,
        "https://api.example.com/aris3/pos/sales/sale-1/actions",
        json={
            "header": {
                "id": "sale-1",
                "tenant_id": "t1",
                "store_id": "s1",
                "status": "PAID",
                "total_due": 10,
                "paid_total": 10,
                "balance_due": 0,
                "change_due": 0,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:01:00Z",
            },
            "lines": [],
            "payments": [],
            "payment_summary": [],
            "refunded_totals": {"subtotal": 0, "restocking_fee": 0, "total": 0},
            "exchanged_totals": {"subtotal": 0, "restocking_fee": 0, "total": 0},
            "net_adjustment": 0,
            "return_events": [],
        },
        status=200,
    )
    responses.add(
        responses.GET,
        "https://api.example.com/aris3/stock",
        json={"code": "PERMISSION_DENIED", "message": "stock denied", "details": None, "trace_id": "trace-s7d7"},
        status=403,
    )

    token = AuthClient(http=http).login("alpha", "pass")
    authed = AuthClient(http=http, access_token=token.access_token)
    me = authed.me()
    assert me.username == "alpha"

    permissions = AccessControlClient(http=http, access_token=token.access_token).effective_permissions()
    assert any(item.key == "stock.view" and item.allowed for item in permissions.permissions)

    stock = StockClient(http=http, access_token=token.access_token)
    table = stock.get_stock(StockQuery())
    assert table.totals.total_units == table.totals.total_rfid + table.totals.total_pending

    import_response = stock.import_epc(
        [
            {
                "sku": "SKU-1",
                "description": "Alpha",
                "var1_value": "BLUE",
                "var2_value": "42",
                "location_code": "SELL-1",
                "pool": "RFID",
                "status": "RFID",
                "qty": 1,
                "epc": "ABCDEFABCDEFABCDEFABCDEF",
            }
        ],
        transaction_id="txn-stock-1",
        idempotency_key="idem-stock-1",
    )
    assert import_response.processed == 1

    cash_client = PosCashClient(http=http, access_token=token.access_token)
    cash_client.cash_action("OPEN", {"transaction_id": "txn-cash-1", "store_id": "s1", "action": "OPEN", "opening_amount": 100, "reason": "alpha"}, idempotency_key="idem-cash-1")

    sales = PosSalesClient(http=http, access_token=token.access_token)
    draft = sales.create_sale({"transaction_id": "txn-pos-1", "store_id": "s1", "lines": []}, idempotency_key="idem-pos-1")
    paid = sales.sale_action(
        draft.header.id,
        "checkout",
        {
            "action": "checkout",
            "transaction_id": "txn-pos-2",
            "payments": [{"method": "CASH", "amount": 10}],
        },
        idempotency_key="idem-pos-2",
    )
    assert paid.header.status == "PAID"

    with pytest.raises(ForbiddenError):
        stock.get_stock(StockQuery(sku="SKU-DENIED"))

    idem_headers = [
        call.request.headers.get("Idempotency-Key")
        for call in responses.calls
        if call.request.method in {"POST", "PATCH"} and "/aris3/" in call.request.url
    ]
    assert "idem-stock-1" in idem_headers
    assert "idem-cash-1" in idem_headers
    assert "idem-pos-1" in idem_headers
    assert "idem-pos-2" in idem_headers
    assert len(audit.rows) >= 6


@pytest.mark.skipif(os.getenv("RUN_STAGING_E2E") != "1", reason="staging e2e disabled")
def test_staging_endpoint_smoke_enabled_by_flag() -> None:
    cfg = load_config()
    assert cfg.api_base_url
