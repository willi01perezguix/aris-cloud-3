from __future__ import annotations

import requests
import responses
from pathlib import Path

from aris3_client_sdk.auth_store import AuthStore
from aris3_client_sdk.clients.auth import AuthClient
from aris3_client_sdk.clients.stock_client import StockClient
from aris3_client_sdk.config import ClientConfig
from aris3_client_sdk.error_mapper import map_error
from aris3_client_sdk.exceptions import (
    AuthError,
    ConflictError,
    MustChangePasswordError,
    PermissionError,
    RateLimitError,
    ServerError,
    TransportError,
)
from aris3_client_sdk.http_client import HttpClient
from aris3_client_sdk.idempotency import idempotency_headers, resolve_idempotency_keys
from aris3_client_sdk.models_stock import StockQuery
from aris3_client_sdk.tracing import TraceContext


def _cfg() -> ClientConfig:
    return ClientConfig(env_name="test", api_base_url="https://api.example.com", retries=2, retry_backoff_seconds=0)


@responses.activate
def test_http_client_retries_get_on_5xx() -> None:
    responses.add(responses.GET, "https://api.example.com/aris3/health", status=503, json={"code": "UNAVAILABLE"})
    responses.add(responses.GET, "https://api.example.com/aris3/health", status=200, json={"ok": True})
    http = HttpClient(_cfg(), trace=TraceContext())

    payload = http.request("GET", "/aris3/health")

    assert payload == {"ok": True}
    assert len(responses.calls) == 2




@responses.activate
def test_http_client_retry_jitter_within_expected_bounds(monkeypatch) -> None:
    cfg = ClientConfig(
        env_name="test",
        api_base_url="https://api.example.com",
        retries=1,
        retry_backoff_seconds=0.2,
        retry_jitter_enabled=True,
        retry_jitter_min_seconds=0.1,
        retry_jitter_max_seconds=0.3,
    )
    http = HttpClient(cfg, trace=TraceContext())

    sleeps: list[float] = []

    def _sleep(value: float) -> None:
        sleeps.append(value)

    monkeypatch.setattr("aris3_client_sdk.http_client.time.sleep", _sleep)
    monkeypatch.setattr("aris3_client_sdk.http_client.random.uniform", lambda a, b: 0.15)

    responses.add(responses.GET, "https://api.example.com/aris3/health", status=503, json={"code": "UNAVAILABLE"})
    responses.add(responses.GET, "https://api.example.com/aris3/health", status=200, json={"ok": True})

    payload = http.request("GET", "/aris3/health")

    assert payload == {"ok": True}
    assert sleeps == [0.35]

def test_http_client_does_not_retry_mutation_by_default(monkeypatch) -> None:
    http = HttpClient(_cfg(), trace=TraceContext())
    attempts = {"count": 0}

    def _request(**_: object):
        attempts["count"] += 1
        raise requests.ConnectionError("boom")

    assert http.session is not None
    monkeypatch.setattr(http.session, "request", _request)

    try:
        http.request("POST", "/aris3/stock/import-sku", json_body={"x": 1})
    except TransportError as exc:
        assert exc.status_code == 0
        assert exc.code == "TRANSPORT_ERROR"
    else:
        raise AssertionError("Expected TransportError")

    assert attempts["count"] == 1


@responses.activate
def test_auth_must_change_password_maps_to_structured_exception() -> None:
    responses.add(
        responses.POST,
        "https://api.example.com/aris3/auth/login",
        status=200,
        json={"access_token": "token", "must_change_password": True, "trace_id": "trace-1"},
    )
    auth = AuthClient(http=HttpClient(_cfg(), trace=TraceContext()))

    try:
        auth.login("u", "p")
    except MustChangePasswordError as exc:
        assert exc.code == "MUST_CHANGE_PASSWORD"
        assert exc.trace_id == "trace-1"
    else:
        raise AssertionError("Expected MustChangePasswordError")


def test_idempotency_helpers_are_consistent() -> None:
    keys = resolve_idempotency_keys(transaction_id="txn-1")
    headers = idempotency_headers(keys)

    assert keys.transaction_id == "txn-1"
    assert headers["Idempotency-Key"] == keys.idempotency_key


def test_error_mapping_matrix() -> None:
    assert isinstance(map_error(401, {"code": "INVALID_TOKEN", "message": "x"}, "t"), AuthError)
    assert isinstance(map_error(403, {"code": "DENIED", "message": "x"}, "t"), PermissionError)
    assert isinstance(map_error(409, {"code": "CONFLICT", "message": "x"}, "t"), ConflictError)
    assert isinstance(map_error(429, {"code": "THROTTLED", "message": "x"}, "t"), RateLimitError)
    assert isinstance(map_error(500, {"code": "SERVER", "message": "x"}, "t"), ServerError)


def test_auth_store_handles_corruption(tmp_path: Path) -> None:
    store = AuthStore(app_name="aris3-test", filename="session.json")
    store._path = lambda: tmp_path / "session.json"  # type: ignore[method-assign]
    store._path().write_text("{not-json")

    assert store.load() is None
    assert not store._path().exists()


@responses.activate
def test_stock_full_table_contract_shape_preserved() -> None:
    responses.add(
        responses.GET,
        "https://api.example.com/aris3/stock",
        status=200,
        json={
            "meta": {"page": 1, "page_size": 50, "sort_by": "sku", "sort_dir": "asc"},
            "rows": [
                {
                    "id": "1",
                    "sku": "SKU-1",
                    "epc": "000000000000000000000001",
                    "location_code": "SELL-01",
                    "pool": "ON_HAND",
                    "status": "ACTIVE",
                    "location_is_vendible": True,
                }
            ],
            "totals": {"total_rows": 1, "total_rfid": 1, "total_pending": 0, "total_units": 1},
        },
    )
    client = StockClient(http=HttpClient(_cfg(), trace=TraceContext()), access_token="t")
    table = client.get_stock(StockQuery(page=1, page_size=50))

    assert table.meta.page == 1
    assert table.rows[0].sku == "SKU-1"
    assert table.totals.total_units == 1
