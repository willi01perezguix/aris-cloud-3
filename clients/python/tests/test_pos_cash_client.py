from __future__ import annotations

import json

import responses

from aris3_client_sdk import load_config
from aris3_client_sdk.clients.pos_cash_client import PosCashClient
from aris3_client_sdk.exceptions import (
    CashDrawerNegativeError,
    CashPermissionDeniedError,
    CashSessionNotOpenError,
)
from aris3_client_sdk.http_client import HttpClient
from aris3_client_sdk.tracing import TraceContext


def _client(base_url: str) -> HttpClient:
    cfg = load_config()
    object.__setattr__(cfg, "api_base_url", base_url)
    return HttpClient(cfg, trace=TraceContext())


def _session_response(session_id: str = "cash-1") -> dict:
    return {
        "id": session_id,
        "tenant_id": "tenant-1",
        "store_id": "store-1",
        "cashier_user_id": "user-1",
        "status": "OPEN",
        "business_date": "2024-01-01",
        "timezone": "UTC",
        "opening_amount": "10.00",
        "expected_cash": "10.00",
        "counted_cash": None,
        "difference": None,
        "opened_at": "2024-01-01T00:00:00Z",
        "closed_at": None,
        "created_at": "2024-01-01T00:00:00Z",
    }


@responses.activate
def test_cash_action_idempotency_header(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    responses.add(
        responses.POST,
        "https://api.example.com/aris3/pos/cash/session/actions",
        json=_session_response(),
        status=200,
    )
    client = PosCashClient(http=http, access_token="token")
    response = client.cash_action(
        "OPEN",
        {
            "transaction_id": "txn-1",
            "store_id": "store-1",
            "action": "OPEN",
            "opening_amount": 10.0,
            "business_date": "2024-01-01",
            "timezone": "UTC",
        },
        idempotency_key="idem-1",
    )
    assert response.id == "cash-1"
    assert responses.calls[0].request.headers["Idempotency-Key"] == "idem-1"


@responses.activate
def test_cash_action_auto_idempotency(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    responses.add(
        responses.POST,
        "https://api.example.com/aris3/pos/cash/session/actions",
        json=_session_response(),
        status=200,
    )
    client = PosCashClient(http=http, access_token="token")
    client.cash_action(
        "CASH_IN",
        {
            "store_id": "store-1",
            "action": "CASH_IN",
            "amount": 5.0,
        },
    )
    body = json.loads(responses.calls[0].request.body.decode("utf-8"))
    assert body["transaction_id"]
    assert "Idempotency-Key" in responses.calls[0].request.headers


@responses.activate
def test_cash_error_mapping(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    responses.add(
        responses.POST,
        "https://api.example.com/aris3/pos/cash/session/actions",
        json={"code": "VALIDATION_ERROR", "message": "Validation error", "details": {"message": "open cash session required"}},
        status=422,
    )
    client = PosCashClient(http=http, access_token="token")
    try:
        client.cash_action("CASH_IN", {"transaction_id": "txn-1", "store_id": "store-1", "action": "CASH_IN", "amount": 1})
    except CashSessionNotOpenError:
        pass
    else:
        raise AssertionError("Expected CashSessionNotOpenError")


@responses.activate
def test_cash_negative_drawer_error(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    responses.add(
        responses.POST,
        "https://api.example.com/aris3/pos/cash/session/actions",
        json={
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": {"message": "cash_out would result in negative expected balance"},
        },
        status=422,
    )
    client = PosCashClient(http=http, access_token="token")
    try:
        client.cash_action(
            "CASH_OUT",
            {"transaction_id": "txn-2", "store_id": "store-1", "action": "CASH_OUT", "amount": 50},
            idempotency_key="idem-2",
        )
    except CashDrawerNegativeError:
        pass
    else:
        raise AssertionError("Expected CashDrawerNegativeError")


@responses.activate
def test_cash_permission_denied(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    responses.add(
        responses.GET,
        "https://api.example.com/aris3/pos/cash/session/current",
        json={"code": "PERMISSION_DENIED", "message": "no", "details": None, "trace_id": "trace"},
        status=403,
    )
    client = PosCashClient(http=http, access_token="token")
    try:
        client.get_current_session(store_id="store-1")
    except CashPermissionDeniedError:
        pass
    else:
        raise AssertionError("Expected CashPermissionDeniedError")
