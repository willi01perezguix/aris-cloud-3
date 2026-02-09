from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ApiError(Exception):
    code: str
    message: str
    details: object | None
    trace_id: str | None
    status_code: int

    def __str__(self) -> str:
        return f"[{self.status_code}] {self.code}: {self.message}"


class UnauthorizedError(ApiError):
    pass


class ForbiddenError(ApiError):
    pass


class NotFoundError(ApiError):
    pass


class ValidationError(ApiError):
    pass


class CashSessionNotOpenError(ApiError):
    pass


class CashDrawerNegativeError(ApiError):
    pass


class CashPermissionDeniedError(ForbiddenError):
    pass
