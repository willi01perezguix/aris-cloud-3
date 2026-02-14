from clients.aris3_client_sdk.stores_client import StoresClient
from clients.aris3_client_sdk.tenants_client import TenantsClient
from clients.aris3_client_sdk.users_client import UsersClient


class DummyHttp:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def request(self, method, path, token=None, json_body=None, headers=None, params=None):
        self.calls.append({"method": method, "path": path, "params": params})
        return {"items": []}


def test_list_query_params_exclude_nulls() -> None:
    http = DummyHttp()

    TenantsClient(http).list_tenants("token", page=1, page_size=10, q=None)
    StoresClient(http).list_stores("token", "tenant-1", page=2, page_size=20, q="abc", status="")
    UsersClient(http).list_users("token", "tenant-1", q="john", role="ADMIN", status=None)

    assert http.calls[0]["params"] == {"page": 1, "page_size": 10}
    assert http.calls[1]["params"] == {"tenant_id": "tenant-1", "page": 2, "page_size": 20, "q": "abc"}
    assert http.calls[2]["params"] == {"tenant_id": "tenant-1", "q": "john", "role": "ADMIN"}
