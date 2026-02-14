from __future__ import annotations

from typing import Any

from clients.aris3_client_sdk.http_client import HttpClient
from clients.aris3_client_sdk.idempotency import build_idempotency_headers


class TenantsClient:
    def __init__(self, http_client: HttpClient) -> None:
        self.http_client = http_client

    def list_tenants(self, access_token: str) -> list[dict[str, Any]]:
        payload = self.http_client.request("GET", "/aris3/admin/tenants", token=access_token)
        return _extract_items(payload)

    def create_tenant(self, access_token: str, tenant_payload: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        return self.http_client.request(
            "POST",
            "/aris3/admin/tenants",
            token=access_token,
            json_body=tenant_payload,
            headers=build_idempotency_headers(idempotency_key),
        )


def _extract_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload.get("items"), list):
        return payload["items"]
    if isinstance(payload.get("data"), list):
        return payload["data"]
    if isinstance(payload.get("tenants"), list):
        return payload["tenants"]
    return []
