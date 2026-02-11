from __future__ import annotations

from dataclasses import dataclass

from ..http_client import HttpClient


@dataclass
class BaseClient:
    http: HttpClient
    access_token: str | None = None
    tenant_id: str | None = None
    app_id: str | None = None
    device_id: str | None = None

    def _auth_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        if self.tenant_id:
            headers["X-Tenant-ID"] = self.tenant_id
        if self.app_id:
            headers["X-App-ID"] = self.app_id
        if self.device_id:
            headers["X-Device-ID"] = self.device_id
        return headers

    def _request(self, method: str, path: str, **kwargs):
        headers = kwargs.pop("headers", {})
        merged = {**self._auth_headers(), **headers}
        return self.http.request(method, path, headers=merged, **kwargs)
