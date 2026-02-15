from __future__ import annotations

import sys
from pathlib import Path

import requests

SDK_SRC = Path(__file__).resolve().parents[1] / "clients" / "python" / "aris3_client_sdk" / "src"
if str(SDK_SRC) not in sys.path:
    sys.path.insert(0, str(SDK_SRC))

from aris3_client_sdk.clients.admin_data_access import AdminDataAccessClient
from aris3_client_sdk.config import ClientConfig
from aris3_client_sdk.exceptions import ApiError, TransportError
from aris3_client_sdk.http_client import HttpClient


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = {}
        self.content = b"{}"
        self.text = ""

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, **kwargs):
        self.calls.append(kwargs)
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _client(session: FakeSession, *, retries: int = 2) -> HttpClient:
    return HttpClient(
        config=ClientConfig(env_name="test", api_base_url="https://example.test", retries=retries, retry_backoff_seconds=0),
        session=session,
    )


def test_error_mapper_normalizes_network_and_conflict_types():
    client = _client(FakeSession([]))

    network = client.normalize_error(
        TransportError(
            code="TRANSPORT_ERROR",
            message="down",
            details=None,
            trace_id="t-1",
            status_code=0,
            raw_payload=None,
        )
    )
    assert network.type == "network"
    assert network.trace_id == "t-1"

    api = ApiError(code="CONFLICT", message="conflict", details=None, trace_id="t-2", status_code=409, raw_payload={})
    normalized = client.normalize_error(api)
    assert normalized.type == "conflict"
    assert normalized.code == "CONFLICT"


def test_cache_invalidated_after_mutation():
    session = FakeSession(
        [
            FakeResponse(200, {"items": [1]}),
            FakeResponse(201, {"id": "new-store"}),
            FakeResponse(200, {"items": [1, 2]}),
        ]
    )
    http = _client(session)
    client = AdminDataAccessClient(http=http, access_token="token")

    assert client.list_stores() == {"items": [1]}
    assert client.list_stores() == {"items": [1]}  # served from cache
    assert len(session.calls) == 1

    mutation = client.create_store(
        {"tenant_id": "tenant-1", "name": "Store 2"},
        idempotency_key="idem-1",
        transaction_id="tx-1",
    )
    mutation.retry()
    assert len(session.calls) == 2

    assert client.list_stores() == {"items": [1, 2]}
    assert len(session.calls) == 3


def test_context_switch_cancels_stale_responses():
    session = FakeSession([FakeResponse(200, {"items": []})])
    http = _client(session)

    version = http.get_context_version("tenant=A")
    http.switch_context("tenant=A")

    try:
        http.request("GET", "/aris3/admin/users", context_key="tenant=A", context_version=version)
        raise AssertionError("expected cancellation")
    except TransportError as exc:
        assert exc.code == "REQUEST_CANCELLED"


def test_retry_policy_get_retries_but_mutation_does_not():
    get_session = FakeSession(
        [
            requests.ConnectionError("boom"),
            FakeResponse(200, {"ok": True}),
        ]
    )
    get_client = _client(get_session, retries=2)
    assert get_client.request("GET", "/health") == {"ok": True}
    assert len(get_session.calls) == 2

    post_session = FakeSession([requests.ConnectionError("boom")])
    post_client = _client(post_session, retries=3)
    try:
        post_client.request("POST", "/aris3/admin/users", json_body={"x": 1})
        raise AssertionError("expected transport error")
    except TransportError:
        pass
    assert len(post_session.calls) == 1

