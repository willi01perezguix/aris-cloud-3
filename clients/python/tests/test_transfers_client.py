from __future__ import annotations

import json

import pytest
import responses

from aris3_client_sdk import load_config
from aris3_client_sdk.clients import transfers_client as transfers_client_module
from aris3_client_sdk.clients.transfers_client import TransfersClient, build_transfer_params
from aris3_client_sdk.exceptions import TransferActionForbiddenError
from aris3_client_sdk.http_client import HttpClient
from aris3_client_sdk.idempotency import IdempotencyKeys
from aris3_client_sdk.models_transfers import TransferQuery
from aris3_client_sdk.tracing import TraceContext


def _client(base_url: str) -> HttpClient:
    cfg = load_config()
    object.__setattr__(cfg, "api_base_url", base_url)
    return HttpClient(cfg, trace=TraceContext())


def test_transfer_query_param_serialization() -> None:
    query = TransferQuery(
        q="Blue",
        status="DRAFT",
        origin_store_id="origin-1",
        from_date="2024-01-01T00:00:00Z",
        page=2,
        sort_order="asc",
    )
    params = build_transfer_params(query)
    assert params["q"] == "Blue"
    assert params["status"] == "DRAFT"
    assert params["origin_store_id"] == "origin-1"
    assert params["from"] == "2024-01-01T00:00:00Z"
    assert params["page"] == 2
    assert params["sort_dir"] == "asc"


@responses.activate
def test_transfer_create_idempotency(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    monkeypatch.setattr(
        transfers_client_module,
        "new_idempotency_keys",
        lambda: IdempotencyKeys(transaction_id="txn-fixed", idempotency_key="idem-fixed"),
    )

    def callback(request):
        payload = json.loads(request.body)
        assert payload["transaction_id"] == "txn-fixed"
        assert request.headers["Idempotency-Key"] == "idem-fixed"
        return (201, {}, json.dumps({"header": {"id": "t1", "tenant_id": "t", "origin_store_id": "o", "destination_store_id": "d", "status": "DRAFT", "created_at": "2024-01-01T00:00:00Z"}, "lines": [], "movement_summary": {"dispatched_lines": 0, "dispatched_qty": 0, "pending_reception": False, "shortages_possible": False}}))

    responses.add_callback(
        responses.POST,
        "https://api.example.com/aris3/transfers",
        callback=callback,
    )

    client = TransfersClient(http=http, access_token="token")
    client.create_transfer(
        {
            "origin_store_id": "o",
            "destination_store_id": "d",
            "lines": [
                {
                    "line_type": "SKU",
                    "qty": 1,
                    "snapshot": {"sku": "SKU-1", "location_code": "LOC", "pool": "P1", "location_is_vendible": True},
                }
            ],
        }
    )


@responses.activate
def test_transfer_action_permission_error(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    responses.add(
        responses.POST,
        "https://api.example.com/aris3/transfers/t1/actions",
        json={"code": "PERMISSION_DENIED", "message": "Permission denied", "details": None, "trace_id": "trace"},
        status=403,
    )
    client = TransfersClient(http=http, access_token="token")
    with pytest.raises(TransferActionForbiddenError) as exc:
        client.transfer_action("t1", "dispatch", {})
    assert exc.value.trace_id == "trace"


@responses.activate
def test_transfer_action_idempotency(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")
    http = _client("https://api.example.com")
    monkeypatch.setattr(
        transfers_client_module,
        "new_idempotency_keys",
        lambda: IdempotencyKeys(transaction_id="txn-fixed", idempotency_key="idem-fixed"),
    )

    def callback(request):
        payload = json.loads(request.body)
        assert payload["transaction_id"] == "txn-fixed"
        assert payload["action"] == "dispatch"
        assert request.headers["Idempotency-Key"] == "idem-fixed"
        return (
            200,
            {},
            json.dumps(
                {
                    "header": {
                        "id": "t1",
                        "tenant_id": "tenant",
                        "origin_store_id": "o",
                        "destination_store_id": "d",
                        "status": "DISPATCHED",
                        "created_at": "2024-01-01T00:00:00Z",
                    },
                    "lines": [],
                    "movement_summary": {
                        "dispatched_lines": 0,
                        "dispatched_qty": 0,
                        "pending_reception": False,
                        "shortages_possible": False,
                    },
                }
            ),
        )

    responses.add_callback(
        responses.POST,
        "https://api.example.com/aris3/transfers/t1/actions",
        callback=callback,
    )
    client = TransfersClient(http=http, access_token="token")
    client.transfer_action("t1", "dispatch", {})
