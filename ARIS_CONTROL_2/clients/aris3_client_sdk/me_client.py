from __future__ import annotations

from clients.aris3_client_sdk.http_client import HttpClient


class MeClient:
    def __init__(self, http_client: HttpClient) -> None:
        self.http_client = http_client

    def get_me(self, access_token: str) -> dict:
        return self.http_client.request("GET", "/aris3/me", token=access_token)
