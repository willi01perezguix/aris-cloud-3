from aris_control_2.clients.aris3_client_sdk.auth_store import AuthStore
from aris_control_2.clients.aris3_client_sdk.modules.stores_client import StoresClient
from aris_control_2.clients.aris3_client_sdk.modules.tenants_client import TenantsClient
from aris_control_2.clients.aris3_client_sdk.modules.users_client import UsersClient


class DummyHttp:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def request(self, method, path, token=None, **kwargs):
        self.calls.append({"method": method, "path": path, "token": token, **kwargs})
        return {}


class DummyAuthStore(AuthStore):
    def __init__(self) -> None:
        super().__init__()
        self.set_token("token-1")


def test_mutations_send_idempotency_key_and_transaction_id() -> None:
    http = DummyHttp()
    auth_store = DummyAuthStore()

    TenantsClient(http=http, auth_store=auth_store).create("Tenant A", "idem-1", "tx-1")
    StoresClient(http=http, auth_store=auth_store).create("tenant-1", "Store A", "idem-2", "tx-2")
    UsersClient(http=http, auth_store=auth_store).create(
        "tenant-1", "a@b.com", "secret123", "store-1", "idem-3", "tx-3"
    )
    UsersClient(http=http, auth_store=auth_store).action("user-1", "set_status", {"status": "ACTIVE"}, "idem-4", "tx-4")

    assert http.calls[0]["headers"]["Idempotency-Key"] == "idem-1"
    assert http.calls[0]["json"]["transaction_id"] == "tx-1"
    assert http.calls[1]["headers"]["Idempotency-Key"] == "idem-2"
    assert http.calls[1]["json"]["transaction_id"] == "tx-2"
    assert http.calls[2]["headers"]["Idempotency-Key"] == "idem-3"
    assert http.calls[2]["json"]["transaction_id"] == "tx-3"
    assert http.calls[3]["headers"]["Idempotency-Key"] == "idem-4"
    assert http.calls[3]["json"]["transaction_id"] == "tx-4"
