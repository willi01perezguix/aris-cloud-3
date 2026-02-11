from __future__ import annotations

from aris3_client_sdk.clients.admin_client import AdminClient


class AdminTenantsService:
    def __init__(self, client: AdminClient) -> None:
        self.client = client

    def list_tenants(self) -> dict:
        return self.client._request("GET", "/aris3/admin/tenants")
