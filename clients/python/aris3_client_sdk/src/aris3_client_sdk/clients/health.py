from __future__ import annotations

from .base import BaseClient


class HealthClient(BaseClient):
    def health(self) -> dict:
        return self.http.request("GET", "/health") or {}
