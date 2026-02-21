from __future__ import annotations

from typing import Mapping

from .exceptions import (
    ApiError,
    AuthError,
    ConflictError,
    NotFoundError,
    PermissionError,
    RateLimitError,
    ServerError,
    ValidationError,
)


def map_error(status_code: int, payload: Mapping[str, object] | None, trace_id: str | None) -> ApiError:
    payload = payload or {}
    code = str(payload.get("code") or "HTTP_ERROR")
    message = str(payload.get("message") or "Request failed")
    details = payload.get("details")
    payload_trace_id = payload.get("trace_id")
    resolved_trace_id = str(payload_trace_id) if payload_trace_id is not None else trace_id
    mapped: type[ApiError]
    if status_code in {401}:
        mapped = AuthError
    elif status_code in {403}:
        mapped = PermissionError
    elif status_code in {404}:
        mapped = NotFoundError
    elif status_code in {400, 422}:
        mapped = ValidationError
    elif status_code == 409:
        mapped = ConflictError
    elif status_code == 429:
        mapped = RateLimitError
    elif status_code >= 500:
        mapped = ServerError
    else:
        mapped = ApiError
    return mapped(
        code=code,
        message=message,
        details=details,
        trace_id=resolved_trace_id,
        status_code=status_code,
        raw_payload=dict(payload),
    )
