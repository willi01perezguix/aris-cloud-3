from __future__ import annotations

from .base import BaseClient
from ..models import TokenResponse, UserResponse


class AuthClient(BaseClient):
    def login(self, username_or_email: str, password: str) -> TokenResponse:
        payload = {"username_or_email": username_or_email, "password": password}
        data = self.http.request("POST", "/aris3/auth/login", json_body=payload)
        return TokenResponse.model_validate(data)

    def change_password(self, current_password: str, new_password: str, idempotency_key: str) -> TokenResponse:
        payload = {"current_password": current_password, "new_password": new_password}
        headers = {"Idempotency-Key": idempotency_key}
        data = self._request("POST", "/aris3/auth/change-password", json_body=payload, headers=headers)
        return TokenResponse.model_validate(data)

    def me(self) -> UserResponse:
        data = self._request("GET", "/aris3/me")
        return UserResponse.model_validate(data)
