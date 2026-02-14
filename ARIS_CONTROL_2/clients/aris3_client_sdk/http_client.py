from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx

from clients.aris3_client_sdk.config import SDKConfig
from clients.aris3_client_sdk.errors import ApiError


class HttpClient:
    def __init__(
        self,
        config: SDKConfig | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.config = config or SDKConfig.from_env()
        self._client = client or httpx.Client(
            base_url=self.config.base_url,
            timeout=self.config.timeout_seconds,
            verify=self.config.verify_ssl,
        )
        self._auth_error_handler: Callable[[ApiError], None] | None = None

    def register_auth_error_handler(self, handler: Callable[[ApiError], None] | None) -> None:
        self._auth_error_handler = handler

    def request(
        self,
        method: str,
        path: str,
        token: str | None = None,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        request_headers = dict(headers or {})
        if token:
            request_headers["Authorization"] = f"Bearer {token}"

        normalized_path = path if path.startswith("/") else f"/{path}"

        try:
            response = self._client.request(
                method=method,
                url=normalized_path,
                json=json_body,
                headers=request_headers,
                params=params,
            )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise ApiError(
                code="NETWORK_ERROR",
                message="Network error while calling ARIS3 API",
                details=str(exc),
                trace_id=None,
                status_code=None,
            ) from exc

        if response.status_code >= 400:
            error = ApiError.from_http_response(response)
            if error.status_code in {401, 403} and self._auth_error_handler:
                self._auth_error_handler(error)
            raise error

        try:
            payload = response.json()
        except ValueError:
            return {}
        return payload if isinstance(payload, dict) else {"data": payload}
