from collections.abc import Iterator

from clients.aris3_client_sdk.errors import ApiError

from aris_control_2.app.admin_console import AdminConsole
from aris_control_2.app.listing_cache import ListingCache
from aris_control_2.app.state import SessionState
from aris_control_2.app.ui.listing_view import ColumnDef


class _StubTenantsClient:
    def __init__(self) -> None:
        self.create_calls = 0

    def create_tenant(self, access_token: str, tenant_payload: dict, idempotency_key: str) -> dict:
        self.create_calls += 1
        return {"ok": True}


class _StubStoresClient:
    pass


class _StubUsersClient:
    pass


def test_listing_cache_respects_ttl_and_expiration() -> None:
    current = [100.0]
    cache = ListingCache(ttl_seconds=15, now=lambda: current[0])

    cache.set("users:key", {"rows": [{"id": 1}]})
    assert cache.get("users:key") is not None

    current[0] = 116.0
    assert cache.get("users:key") is None


def test_refresh_keeps_filters_and_page_state(monkeypatch) -> None:
    console = AdminConsole(tenants=_StubTenantsClient(), stores=_StubStoresClient(), users=_StubUsersClient())
    session = SessionState(
        access_token="token",
        role="SUPERADMIN",
        effective_tenant_id="tenant-1",
        selected_tenant_id="tenant-1",
        filters_by_module={"tenants": {"q": "north"}},
        pagination_by_module={"tenants": {"page": 3, "page_size": 20}},
    )

    calls = {"count": 0}

    def _fetch(page: int, page_size: int) -> dict:
        calls["count"] += 1
        return {"rows": [{"id": "tenant-1"}], "page": page, "page_size": page_size, "total": 1}

    answers: Iterator[str] = iter(["r", "b"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    console._run_listing_loop(
        module="tenants",
        session=session,
        fetch_page=_fetch,
        columns=[ColumnDef("id", "id")],
        filter_keys=["q"],
    )

    assert calls["count"] >= 2
    assert session.filters_by_module["tenants"] == {"q": "north"}
    assert session.pagination_by_module["tenants"] == {"page": 3, "page_size": 20}


def test_cache_invalidated_after_mutation() -> None:
    console = AdminConsole(tenants=_StubTenantsClient(), stores=_StubStoresClient(), users=_StubUsersClient())
    session = SessionState(access_token="token", role="SUPERADMIN", effective_tenant_id="tenant-1", selected_tenant_id="tenant-1")

    def _fetch(page: int, page_size: int) -> dict:
        return {"rows": [{"id": "tenant-1"}], "page": page, "page_size": page_size, "total": 1}

    first = console._fetch_listing_with_cache("tenants", session, 1, 20, _fetch, force_refresh=False)
    assert first["total"] == 1

    console._invalidate_read_cache("tenants")

    key = console._cache_key("tenants", session, 1, 20)
    assert console._listing_cache.get(key) is None


def test_retryable_errors_only_for_transient_get() -> None:
    assert AdminConsole._is_retryable_listing_error(ApiError(code="NETWORK_ERROR", message="offline", status_code=None))
    assert AdminConsole._is_retryable_listing_error(ApiError(code="HTTP_ERROR", message="server", status_code=503))
    assert not AdminConsole._is_retryable_listing_error(ApiError(code="HTTP_ERROR", message="bad request", status_code=400))
