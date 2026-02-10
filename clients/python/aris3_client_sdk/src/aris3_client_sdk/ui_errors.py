from __future__ import annotations

from dataclasses import dataclass

from .exceptions import ApiError


@dataclass(frozen=True)
class UserFacingError:
    message: str
    details: str | None = None
    trace_id: str | None = None

    @property
    def technical_details(self) -> str | None:
        if self.details:
            return self.details
        return None


def to_user_facing_error(exc: ApiError) -> UserFacingError:
    primary = exc.message.strip() or "Request failed"
    details = f"{exc.code} (HTTP {exc.status_code})"
    if exc.details:
        details = f"{details}: {exc.details}"
    return UserFacingError(message=primary, details=details, trace_id=exc.trace_id)
