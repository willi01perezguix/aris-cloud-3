from __future__ import annotations

from dataclasses import dataclass

from ..http_client import HttpClient


@dataclass
class BaseClient:
    http: HttpClient
    access_token: str | None = None

    def _auth_headers(self) -> dict[str, str]:
        if not self.access_token:
            return {}
        return {"Authorization": f"Bearer {self.access_token}"}

    def _request(self, method: str, path: str, **kwargs):
        headers = kwargs.pop("headers", {})
        merged = {**self._auth_headers(), **headers}
        return self.http.request(method, path, headers=merged, **kwargs)
