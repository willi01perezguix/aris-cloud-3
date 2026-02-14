from aris_control_2.app.infrastructure.idempotency.key_factory import IdempotencyKeyFactory
from aris_control_2.clients.aris3_client_sdk.auth_store import AuthStore
from aris_control_2.clients.aris3_client_sdk.http_client import HttpClient


class UsersClient:
    def __init__(self, http: HttpClient, auth_store: AuthStore) -> None:
        self.http = http
        self.auth_store = auth_store

    def list(self, tenant_id: str) -> list[dict]:
        result = self.http.request("GET", f"/admin/tenants/{tenant_id}/users", token=self.auth_store.get_token())
        return result.get("items", [])

    def create(self, tenant_id: str, email: str, password: str) -> dict:
        headers = {"Idempotency-Key": IdempotencyKeyFactory.new_key("user")}
        return self.http.request(
            "POST",
            f"/admin/tenants/{tenant_id}/users",
            token=self.auth_store.get_token(),
            headers=headers,
            json={"email": email, "password": password},
        )
