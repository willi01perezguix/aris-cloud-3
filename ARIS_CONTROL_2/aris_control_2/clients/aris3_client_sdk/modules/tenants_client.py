from aris_control_2.clients.aris3_client_sdk.auth_store import AuthStore
from aris_control_2.clients.aris3_client_sdk.http_client import HttpClient


class TenantsClient:
    def __init__(self, http: HttpClient, auth_store: AuthStore) -> None:
        self.http = http
        self.auth_store = auth_store

    def list(self) -> list[dict]:
        result = self.http.request("GET", "/aris3/admin/tenants", token=self.auth_store.get_token())
        return result.get("items", [])

    def create(self, name: str, idempotency_key: str) -> dict:
        headers = {"Idempotency-Key": idempotency_key}
        return self.http.request(
            "POST",
            "/aris3/admin/tenants",
            token=self.auth_store.get_token(),
            headers=headers,
            json={"name": name},
        )
