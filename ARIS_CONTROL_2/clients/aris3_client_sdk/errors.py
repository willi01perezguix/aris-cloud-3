from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class ApiError(Exception):
    code: str
    message: str
    details: dict[str, Any] | list[Any] | str | None = None
    trace_id: str | None = None
    status_code: int | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"

    @classmethod
    def from_http_response(cls, response: httpx.Response) -> "ApiError":
        trace_id = _extract_trace_id(response)
        try:
            payload = response.json()
        except ValueError:
            return cls(
                code="HTTP_ERROR",
                message=response.text or "HTTP request failed",
                details=None,
                trace_id=trace_id,
                status_code=response.status_code,
            )

        if isinstance(payload, dict):
            return cls(
                code=str(payload.get("code") or "HTTP_ERROR"),
                message=str(payload.get("message") or response.text or "HTTP request failed"),
                details=payload.get("details"),
                trace_id=payload.get("trace_id") or trace_id,
                status_code=response.status_code,
            )

        return cls(
            code="HTTP_ERROR",
            message=response.text or "HTTP request failed",
            details=payload,
            trace_id=trace_id,
            status_code=response.status_code,
        )


def _extract_trace_id(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
        if isinstance(payload, dict) and payload.get("trace_id"):
            return str(payload["trace_id"])
    except ValueError:
        pass
    return response.headers.get("X-Trace-ID") or response.headers.get("X-Trace-Id")
