from __future__ import annotations

from typing import Any

from clients.aris3_client_sdk.http_client import HttpClient
from clients.aris3_client_sdk.idempotency import build_idempotency_headers


class UsersClient:
    def __init__(self, http_client: HttpClient) -> None:
        self.http_client = http_client

    def list_users(self, access_token: str, tenant_id: str) -> list[dict[str, Any]]:
        payload = self.http_client.request(
            "GET",
            "/aris3/admin/users",
            token=access_token,
            params={"tenant_id": tenant_id},
        )
        return _extract_items(payload)

    def create_user(self, access_token: str, user_payload: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        return self.http_client.request(
            "POST",
            "/aris3/admin/users",
            token=access_token,
            json_body=user_payload,
            headers=build_idempotency_headers(idempotency_key),
        )

    def user_action(
        self,
        access_token: str,
        user_id: str,
        action: str,
        action_payload: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        body = {"action": action, **action_payload}
        return self.http_client.request(
            "POST",
            f"/aris3/admin/users/{user_id}/actions",
            token=access_token,
            json_body=body,
            headers=build_idempotency_headers(idempotency_key),
        )


def _extract_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload.get("items"), list):
        return payload["items"]
    if isinstance(payload.get("data"), list):
        return payload["data"]
    if isinstance(payload.get("users"), list):
        return payload["users"]
    return []
