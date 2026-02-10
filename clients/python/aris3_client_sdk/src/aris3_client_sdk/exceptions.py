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
        trace = f" trace_id={self.trace_id}" if self.trace_id else ""
        return f"[{self.status_code}] {self.code}: {self.message}{trace}"


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


class TransferStateError(ValidationError):
    pass


class TransferTenantMismatchError(ForbiddenError):
    pass


class TransferActionForbiddenError(ForbiddenError):
    pass


class InventoryCountStateError(ValidationError):
    pass


class InventoryCountLockConflictError(ValidationError):
    pass


class InventoryCountActionForbiddenError(ForbiddenError):
    pass


class InventoryCountClosedError(ValidationError):
    pass
