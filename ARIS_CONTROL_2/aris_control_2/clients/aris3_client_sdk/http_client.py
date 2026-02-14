import time
from dataclasses import dataclass
from typing import Any, Callable

import httpx


@dataclass
class APIError(Exception):
    code: str
    message: str
    details: dict[str, Any] | None = None
    trace_id: str | None = None
    status_code: int | None = None


class HttpClient:
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 20,
        verify_ssl: bool = True,
        retry_max_attempts: int = 3,
        retry_backoff_ms: int = 150,
        transport: Callable[..., httpx.Response] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.verify_ssl = verify_ssl
        self.retry_max_attempts = max(1, retry_max_attempts)
        self.retry_backoff_ms = max(0, retry_backoff_ms)
        self.transport = transport or httpx.request

    def request(self, method: str, path: str, token: str | None = None, **kwargs: Any) -> dict[str, Any]:
        headers = kwargs.pop("headers", {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
        url = f"{self.base_url}{path}"

        allow_retry = method.upper() == "GET"

        for attempt in range(1, self.retry_max_attempts + 1):
            try:
                response = self.transport(
                    method,
                    url,
                    timeout=self.timeout_seconds,
                    verify=self.verify_ssl,
                    headers=headers,
                    **kwargs,
                )
            except httpx.TimeoutException as exc:
                if (not allow_retry) or attempt >= self.retry_max_attempts:
                    raise APIError(
                        code="TIMEOUT_ERROR",
                        message="La solicitud excedió el tiempo de espera. Verifica tu red y vuelve a intentar.",
                        status_code=None,
                    ) from exc
                self._backoff(attempt)
                continue
            except httpx.TransportError as exc:
                if (not allow_retry) or attempt >= self.retry_max_attempts:
                    raise APIError(
                        code="NETWORK_ERROR",
                        message="No se pudo conectar con ARIS3 API. Reintenta manualmente.",
                        status_code=None,
                    ) from exc
                self._backoff(attempt)
                continue

            if response.status_code >= 400:
                payload = self._safe_json(response)
                api_error = APIError(
                    code=payload.get("code", "HTTP_ERROR"),
                    message=payload.get("message", response.text),
                    details=payload.get("details"),
                    trace_id=payload.get("trace_id") or response.headers.get("X-Trace-ID") or response.headers.get("X-Trace-Id"),
                    status_code=response.status_code,
                )
                if allow_retry and self._is_retryable_status(response.status_code) and attempt < self.retry_max_attempts:
                    self._backoff(attempt)
                    continue
                raise api_error
            return self._safe_json(response)
        raise APIError(code="INTERNAL_ERROR", message="Max retry attempts reached")

    def _backoff(self, attempt: int) -> None:
        time.sleep((self.retry_backoff_ms * attempt) / 1000)

    @staticmethod
    def _is_retryable_status(status_code: int) -> bool:
        return 500 <= status_code <= 599

    @staticmethod
    def _safe_json(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
            return payload if isinstance(payload, dict) else {"items": payload}
        except ValueError:
            return {"message": response.text}
