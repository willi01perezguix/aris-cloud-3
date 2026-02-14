import os
from dataclasses import dataclass
from typing import Any, Callable

import httpx


@dataclass
class APIError(Exception):
    code: str
    message: str
    details: dict[str, Any] | None = None
    trace_id: str | None = None


class HttpClient:
    def __init__(
        self,
        base_url: str,
        timeout_seconds: int = 30,
        verify_ssl: bool = True,
        transport: Callable[..., httpx.Response] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.verify_ssl = verify_ssl
        self.transport = transport or httpx.request

    @classmethod
    def from_env(cls) -> "HttpClient":
        return cls(
            base_url=os.getenv("ARIS3_BASE_URL", "http://localhost:8000"),
            timeout_seconds=int(os.getenv("ARIS3_TIMEOUT_SECONDS", "30")),
            verify_ssl=os.getenv("ARIS3_VERIFY_SSL", "true").lower() == "true",
        )

    def request(self, method: str, path: str, token: str | None = None, **kwargs: Any) -> dict[str, Any]:
        headers = kwargs.pop("headers", {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
        response = self.transport(
            method,
            f"{self.base_url}{path}",
            timeout=self.timeout_seconds,
            verify=self.verify_ssl,
            headers=headers,
            **kwargs,
        )
        if response.status_code >= 400:
            payload = self._safe_json(response)
            raise APIError(
                code=payload.get("code", "HTTP_ERROR"),
                message=payload.get("message", response.text),
                details=payload.get("details"),
                trace_id=payload.get("trace_id") or response.headers.get("X-Trace-Id"),
            )
        return self._safe_json(response)

    @staticmethod
    def _safe_json(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
            return payload if isinstance(payload, dict) else {"items": payload}
        except ValueError:
            return {"message": response.text}
