from __future__ import annotations

import pytest
import responses

from aris3_client_sdk import load_config
from aris3_client_sdk.clients import inventory_counts_client as inv_module
from aris3_client_sdk.clients.inventory_counts_client import InventoryCountsClient
from aris3_client_sdk.exceptions import (
    InventoryCountActionForbiddenError,
    InventoryCountLockConflictError,
)
from aris3_client_sdk.http_client import HttpClient
from aris3_client_sdk.idempotency import IdempotencyKeys
from aris3_client_sdk.tracing import TraceContext


def _client(base_url: str) -> HttpClient:
    cfg = load_config()
    object.__setattr__(cfg, "api_base_url", base_url)
    return HttpClient(cfg, trace=TraceContext())


@responses.activate
def test_lifecycle_happy_path(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    monkeypatch.setattr(
        inv_module,
        "new_idempotency_keys",
        lambda: IdempotencyKeys(transaction_id="txn-fixed", idempotency_key="idem-fixed"),
    )
    http = _client("https://api.example.com")
    client = InventoryCountsClient(http=http, access_token="token")

    responses.add(
        responses.POST,
        "https://api.example.com/aris3/inventory-counts",
        json={"header": {"id": "c1", "store_id": "s1", "state": "ACTIVE", "lock_active": True}},
        status=201,
    )
    responses.add(
        responses.POST,
        "https://api.example.com/aris3/inventory-counts/c1/scan-batches",
        json={"count_id": "c1", "accepted": 1, "rejected": 0, "line_results": []},
        status=200,
    )
    responses.add(
        responses.POST,
        "https://api.example.com/aris3/inventory-counts/c1/actions",
        json={"header": {"id": "c1", "store_id": "s1", "state": "CLOSED"}},
        status=200,
    )

    created = client.create_or_start_count({"store_id": "s1"})
    assert created.id == "c1"

    submitted = client.submit_scan_batch("c1", {"items": [{"sku": "SKU-1", "qty": 1}]})
    assert submitted.accepted == 1

    closed = client.count_action("c1", "CLOSE", {"action": "CLOSE"}, current_state="ACTIVE")
    assert closed.state == "CLOSED"


@responses.activate
def test_pause_resume_and_summary_difference_fetch(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    client = InventoryCountsClient(http=http, access_token="token")
    responses.add(
        responses.POST,
        "https://api.example.com/aris3/inventory-counts/c1/actions",
        json={"header": {"id": "c1", "store_id": "s1", "state": "PAUSED"}},
        status=200,
    )
    responses.add(
        responses.GET,
        "https://api.example.com/aris3/inventory-counts/c1/summary",
        json={"count_id": "c1", "expected_units": 10, "counted_units": 8, "variance_units": -2},
        status=200,
    )
    responses.add(
        responses.GET,
        "https://api.example.com/aris3/inventory-counts/c1/differences",
        json={"count_id": "c1", "rows": [{"sku": "SKU-1", "expected_qty": 10, "counted_qty": 8, "delta_qty": -2}]},
        status=200,
    )

    paused = client.count_action("c1", "PAUSE", {"action": "PAUSE"}, current_state="ACTIVE")
    assert paused.state == "PAUSED"
    assert client.get_count_summary("c1").variance_units == -2
    assert client.get_count_differences("c1").rows[0].sku == "SKU-1"


@responses.activate
def test_invalid_transition_handling(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    client = InventoryCountsClient(http=http, access_token="token")
    with pytest.raises(ValueError):
        client.count_action("c1", "PAUSE", {"action": "PAUSE"}, current_state="CLOSED")


@responses.activate
def test_forbidden_action_and_lock_conflict(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    client = InventoryCountsClient(http=http, access_token="token")

    responses.add(
        responses.POST,
        "https://api.example.com/aris3/inventory-counts/c1/actions",
        json={"code": "PERMISSION_DENIED", "message": "Permission denied", "details": None, "trace_id": "t-1"},
        status=403,
    )
    with pytest.raises(InventoryCountActionForbiddenError) as forbidden:
        client.count_action("c1", "CANCEL", {"action": "CANCEL"}, current_state="ACTIVE")
    assert forbidden.value.trace_id == "t-1"

    responses.reset()
    responses.add(
        responses.POST,
        "https://api.example.com/aris3/inventory-counts/c1/scan-batches",
        json={"code": "INVALID_STATE", "message": "store lock conflict", "details": None, "trace_id": "t-2"},
        status=422,
    )
    with pytest.raises(InventoryCountLockConflictError) as locked:
        client.submit_scan_batch("c1", {"items": [{"sku": "S", "qty": 1}]})
    assert locked.value.trace_id == "t-2"


@responses.activate
def test_export_not_available_returns_none(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    client = InventoryCountsClient(http=http, access_token="token")
    responses.add(
        responses.GET,
        "https://api.example.com/aris3/inventory-counts/c1/export",
        json={"code": "NOT_FOUND", "message": "missing", "details": None, "trace_id": "t"},
        status=404,
    )
    assert client.export_count_result("c1") is None
