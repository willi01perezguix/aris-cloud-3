from aris_control_2.clients.aris3_client_sdk.auth_store import AuthStore
from aris_control_2.clients.aris3_client_sdk.http_client import HttpClient


class StoresClient:
    def __init__(self, http: HttpClient, auth_store: AuthStore) -> None:
        self.http = http
        self.auth_store = auth_store

    def list(self, tenant_id: str) -> list[dict]:
        result = self.http.request(
            "GET", f"/aris3/admin/tenants/{tenant_id}/stores", token=self.auth_store.get_token()
        )
        return result.get("items", [])

    def create(self, tenant_id: str, name: str, idempotency_key: str, transaction_id: str) -> dict:
        headers = {"Idempotency-Key": idempotency_key}
        return self.http.request(
            "POST",
            f"/aris3/admin/tenants/{tenant_id}/stores",
            token=self.auth_store.get_token(),
            headers=headers,
            json={"name": name, "transaction_id": transaction_id},
        )
