from clients.aris3_client_sdk.errors import ApiError
from clients.aris3_client_sdk.stores_client import StoresClient
from clients.aris3_client_sdk.tenants_client import TenantsClient
from clients.aris3_client_sdk.users_client import UsersClient


class DummyHttp:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def request(self, method, path, token=None, json_body=None, headers=None, params=None):
        self.calls.append(
            {
                "method": method,
                "path": path,
                "token": token,
                "json_body": json_body,
                "headers": headers,
                "params": params,
            }
        )
        return {"items": []}


class ErrorHttp:
    def request(self, method, path, token=None, json_body=None, headers=None, params=None):
        raise ApiError(
            code="FORBIDDEN",
            message="forbidden",
            status_code=403,
            details=None,
            trace_id="trace-123",
        )


def test_admin_clients_paths_and_methods_and_idempotency_headers() -> None:
    http = DummyHttp()
    tenants = TenantsClient(http)
    stores = StoresClient(http)
    users = UsersClient(http)

    tenants.list_tenants("tkn")
    tenants.create_tenant("tkn", {"code": "TEN", "name": "Tenant"}, "idem-1")
    stores.list_stores("tkn", "tenant-1")
    stores.create_store("tkn", {"tenant_id": "tenant-1", "code": "S1", "name": "Store"}, "idem-2")
    users.list_users("tkn", "tenant-1")
    users.create_user(
        "tkn",
        {"tenant_id": "tenant-1", "store_id": "store-1", "username": "u", "email": "u@x", "role": "ADMIN"},
        "idem-3",
    )
    users.user_action("tkn", "user-1", "set_status", {"status": "ACTIVE"}, "idem-4")

    assert http.calls[0]["method"] == "GET" and http.calls[0]["path"] == "/aris3/admin/tenants"
    assert http.calls[1]["method"] == "POST" and http.calls[1]["path"] == "/aris3/admin/tenants"
    assert http.calls[1]["headers"]["Idempotency-Key"] == "idem-1"
    assert http.calls[1]["headers"]["X-Idempotency-Key"] == "idem-1"
    assert http.calls[2]["method"] == "GET" and http.calls[2]["path"] == "/aris3/admin/stores"
    assert http.calls[2]["params"] == {"tenant_id": "tenant-1"}
    assert http.calls[3]["method"] == "POST" and http.calls[3]["path"] == "/aris3/admin/stores"
    assert http.calls[4]["method"] == "GET" and http.calls[4]["path"] == "/aris3/admin/users"
    assert http.calls[5]["method"] == "POST" and http.calls[5]["path"] == "/aris3/admin/users"
    assert http.calls[6]["method"] == "POST" and http.calls[6]["path"] == "/aris3/admin/users/user-1/actions"


def test_api_error_keeps_trace_id() -> None:
    client = TenantsClient(ErrorHttp())

    try:
        client.list_tenants("token")
        assert False, "Expected ApiError"
    except ApiError as exc:
        assert exc.status_code == 403
        assert exc.trace_id == "trace-123"
