from __future__ import annotations

from typing import Mapping

from .exceptions import (
    ApiError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)


def map_error(status_code: int, payload: Mapping[str, object] | None, trace_id: str | None) -> ApiError:
    payload = payload or {}
    code = str(payload.get("code") or "HTTP_ERROR")
    message = str(payload.get("message") or "Request failed")
    details = payload.get("details")
    mapped: type[ApiError]
    if status_code in {401}:
        mapped = UnauthorizedError
    elif status_code in {403}:
        mapped = ForbiddenError
    elif status_code in {404}:
        mapped = NotFoundError
    elif status_code in {400, 422}:
        mapped = ValidationError
    else:
        mapped = ApiError
    return mapped(code=code, message=message, details=details, trace_id=trace_id, status_code=status_code)
