from __future__ import annotations

from clients.aris3_client_sdk.http_client import HttpClient


class AuthClient:
    def __init__(self, http_client: HttpClient) -> None:
        self.http_client = http_client

    def login(self, username_or_email: str, password: str) -> dict:
        payload = {"username_or_email": username_or_email, "password": password}
        response = self.http_client.request("POST", "/aris3/auth/login", json_body=payload)
        return {
            "access_token": response.get("access_token"),
            "refresh_token": response.get("refresh_token"),
            "must_change_password": bool(response.get("must_change_password", False)),
            **response,
        }
