from __future__ import annotations

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

    def request(
        self,
        method: str,
        path: str,
        token: str | None = None,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
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
            raise ApiError.from_http_response(response)

        try:
            payload = response.json()
        except ValueError:
            return {}
        return payload if isinstance(payload, dict) else {"data": payload}
