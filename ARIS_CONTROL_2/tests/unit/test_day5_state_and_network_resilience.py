from __future__ import annotations

import httpx

from clients.aris3_client_sdk.config import SDKConfig
from clients.aris3_client_sdk.errors import ApiError
from clients.aris3_client_sdk.http_client import HttpClient

from aris_control_2.app.admin_console import AdminConsole
from aris_control_2.app.operational_support import OperationalSupportCenter
from aris_control_2.app.state import SessionState


class _StubClient:
    pass


def test_apply_me_resets_operational_context_on_tenant_change() -> None:
    session = SessionState(
        role="ADMIN",
        effective_tenant_id="tenant-a",
        selected_tenant_id="tenant-a",
        filters_by_module={"stores": {"status": "ACTIVE"}},
        pagination_by_module={"stores": {"page": 3, "page_size": 20}},
        listing_view_by_module={"stores": {"visible_columns": ["id"]}},
    )

    session.apply_me({"role": "ADMIN", "effective_tenant_id": "tenant-b"})

    assert session.effective_tenant_id == "tenant-b"
    assert session.selected_tenant_id == "tenant-b"
    assert session.filters_by_module == {}
    assert session.pagination_by_module == {}
    assert session.listing_view_by_module == {}


def test_listing_retry_keeps_filters_and_recovers(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ARIS3_INCIDENTS_PATH", str(tmp_path / "incidents.json"))
    support = OperationalSupportCenter.load()
    console = AdminConsole(tenants=_StubClient(), stores=_StubClient(), users=_StubClient(), support_center=support)
    session = SessionState(
        access_token="token",
        role="SUPERADMIN",
        effective_tenant_id="tenant-1",
        selected_tenant_id="tenant-1",
        filters_by_module={"users": {"q": "ana", "status": "ACTIVE"}},
        pagination_by_module={"users": {"page": 2, "page_size": 20}},
    )

    calls = {"count": 0}

    def _fetch(page: int, page_size: int) -> dict:
        calls["count"] += 1
        if calls["count"] == 1:
            raise ApiError(code="NETWORK_ERROR", message="offline")
        return {"rows": [{"id": "u-1"}], "page": page, "page_size": page_size, "total": 1}

    listing = console._fetch_listing_with_cache("users", session, 2, 20, _fetch, force_refresh=True)

    assert listing["total"] == 1
    assert calls["count"] == 2
    assert session.filters_by_module["users"] == {"q": "ana", "status": "ACTIVE"}
    assert session.pagination_by_module["users"] == {"page": 2, "page_size": 20}


def test_http_client_retries_get_not_post() -> None:
    call_log: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        call_log.append(f"{request.method}:{request.url.path}")
        if request.url.path == "/health" and len(call_log) == 1:
            raise httpx.ReadTimeout("slow")
        if request.url.path == "/health":
            return httpx.Response(200, json={"ok": True})
        raise httpx.ReadTimeout("write timeout")

    transport = httpx.MockTransport(handler)
    http = HttpClient(
        config=SDKConfig(
            base_url="https://example.test/",
            timeout_seconds=5,
            verify_ssl=True,
            retry_max_attempts=3,
            retry_backoff_ms=0,
        ),
        client=httpx.Client(base_url="https://example.test/", transport=transport),
    )

    assert http.request("GET", "/health")["ok"] is True

    try:
        http.request("POST", "/tenants", json_body={"code": "T1"})
        raised = False
    except ApiError as error:
        raised = True
        assert error.code == "NETWORK_ERROR"

    assert raised
    assert call_log == ["GET:/health", "GET:/health", "POST:/tenants"]
