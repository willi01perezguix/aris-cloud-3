from __future__ import annotations

from typing import Any

from clients.aris3_client_sdk.http_client import HttpClient
from clients.aris3_client_sdk.idempotency import build_idempotency_headers
from clients.aris3_client_sdk.normalizers import normalize_listing


class TenantsClient:
    def __init__(self, http_client: HttpClient) -> None:
        self.http_client = http_client

    def list_tenants(
        self,
        access_token: str,
        page: int | None = None,
        page_size: int | None = None,
        q: str | None = None,
    ) -> dict[str, Any]:
        params = _build_query_params(page=page, page_size=page_size, q=q)
        payload = self.http_client.request("GET", "/aris3/admin/tenants", token=access_token, params=params)
        return normalize_listing(payload, page=page or 1, page_size=page_size or 20)

    def create_tenant(self, access_token: str, tenant_payload: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        return self.http_client.request(
            "POST",
            "/aris3/admin/tenants",
            token=access_token,
            json_body=tenant_payload,
            headers=build_idempotency_headers(idempotency_key),
        )


def _build_query_params(**kwargs: Any) -> dict[str, Any]:
    return {key: value for key, value in kwargs.items() if value not in (None, "")}
