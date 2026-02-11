from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ApiError(Exception):
    code: str
    message: str
    details: object | None
    trace_id: str | None
    status_code: int
    raw_payload: object | None = None

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


class AuthError(UnauthorizedError):
    """Authentication failed or session is invalid."""


class PermissionError(ForbiddenError):
    """Authorization denied by RBAC or tenant ceiling."""


class ConflictError(ApiError):
    """409 or conflict-style errors."""


class RateLimitError(ApiError):
    """429 throttling error."""


class ServerError(ApiError):
    """5xx server-side failures."""


class TransportError(ApiError):
    """Network/transport failure before an HTTP response was returned."""


class MustChangePasswordError(AuthError):
    """Login succeeded with must_change_password=true policy response."""


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
