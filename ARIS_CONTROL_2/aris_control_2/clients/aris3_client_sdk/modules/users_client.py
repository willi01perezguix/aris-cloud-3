from aris_control_2.clients.aris3_client_sdk.auth_store import AuthStore
from aris_control_2.clients.aris3_client_sdk.http_client import HttpClient


class UsersClient:
    def __init__(self, http: HttpClient, auth_store: AuthStore) -> None:
        self.http = http
        self.auth_store = auth_store

    def list(self, tenant_id: str) -> list[dict]:
        result = self.http.request("GET", f"/aris3/admin/tenants/{tenant_id}/users", token=self.auth_store.get_token())
        return result.get("items", [])

    def create(self, tenant_id: str, email: str, password: str, store_id: str | None, idempotency_key: str) -> dict:
        headers = {"Idempotency-Key": idempotency_key}
        payload = {"email": email, "password": password}
        if store_id:
            payload["store_id"] = store_id
        return self.http.request(
            "POST",
            f"/aris3/admin/tenants/{tenant_id}/users",
            token=self.auth_store.get_token(),
            headers=headers,
            json=payload,
        )

    def action(self, user_id: str, action: str, payload: dict, idempotency_key: str) -> dict:
        headers = {"Idempotency-Key": idempotency_key}
        return self.http.request(
            "POST",
            f"/aris3/admin/users/{user_id}/actions",
            token=self.auth_store.get_token(),
            headers=headers,
            json={"action": action, **payload},
        )
