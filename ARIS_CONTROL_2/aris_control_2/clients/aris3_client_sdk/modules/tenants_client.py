from aris_control_2.app.infrastructure.idempotency.key_factory import IdempotencyKeyFactory
from aris_control_2.clients.aris3_client_sdk.auth_store import AuthStore
from aris_control_2.clients.aris3_client_sdk.http_client import HttpClient


class TenantsClient:
    def __init__(self, http: HttpClient, auth_store: AuthStore) -> None:
        self.http = http
        self.auth_store = auth_store

    def list(self) -> list[dict]:
        result = self.http.request("GET", "/admin/tenants", token=self.auth_store.get_token())
        return result.get("items", [])

    def create(self, name: str) -> dict:
        headers = {"Idempotency-Key": IdempotencyKeyFactory.new_key("tenant")}
        return self.http.request(
            "POST",
            "/admin/tenants",
            token=self.auth_store.get_token(),
            headers=headers,
            json={"name": name},
        )
