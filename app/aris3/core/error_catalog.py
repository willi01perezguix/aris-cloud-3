from dataclasses import dataclass
from fastapi import status


@dataclass(frozen=True)
class ErrorDefinition:
    code: str
    message: str
    status_code: int


class ErrorCatalog:
    INVALID_TOKEN = ErrorDefinition("INVALID_TOKEN", "Invalid token", status.HTTP_401_UNAUTHORIZED)
    INVALID_CREDENTIALS = ErrorDefinition(
        "INVALID_CREDENTIALS",
        "Invalid credentials",
        status.HTTP_401_UNAUTHORIZED,
    )
    USER_INACTIVE = ErrorDefinition(
        "USER_INACTIVE",
        "User is inactive or suspended",
        status.HTTP_403_FORBIDDEN,
    )
    PERMISSION_DENIED = ErrorDefinition(
        "PERMISSION_DENIED",
        "Permission denied",
        status.HTTP_403_FORBIDDEN,
    )
    CURRENT_PASSWORD_INVALID = ErrorDefinition(
        "CURRENT_PASSWORD_INVALID",
        "Current password invalid",
        status.HTTP_400_BAD_REQUEST,
    )
    PASSWORD_TOO_SHORT = ErrorDefinition(
        "PASSWORD_TOO_SHORT",
        "Password too short",
        status.HTTP_400_BAD_REQUEST,
    )
    PASSWORD_MUST_DIFFER = ErrorDefinition(
        "PASSWORD_MUST_DIFFER",
        "New password must differ from current password",
        status.HTTP_400_BAD_REQUEST,
    )
    PASSWORD_COMPLEXITY = ErrorDefinition(
        "PASSWORD_COMPLEXITY",
        "Password must include letters and numbers",
        status.HTTP_400_BAD_REQUEST,
    )
    TENANT_SCOPE_REQUIRED = ErrorDefinition(
        "TENANT_SCOPE_REQUIRED",
        "Tenant scope is required",
        status.HTTP_403_FORBIDDEN,
    )
    CROSS_TENANT_ACCESS_DENIED = ErrorDefinition(
        "CROSS_TENANT_ACCESS_DENIED",
        "Cross-tenant access denied",
        status.HTTP_403_FORBIDDEN,
    )
    STORE_SCOPE_REQUIRED = ErrorDefinition(
        "STORE_SCOPE_REQUIRED",
        "Store scope is required",
        status.HTTP_403_FORBIDDEN,
    )
    STORE_SCOPE_MISMATCH = ErrorDefinition(
        "STORE_SCOPE_MISMATCH",
        "Store scope mismatch",
        status.HTTP_403_FORBIDDEN,
    )
    TENANT_STORE_MISMATCH = ErrorDefinition(
        "TENANT_STORE_MISMATCH",
        "Store does not belong to tenant",
        status.HTTP_403_FORBIDDEN,
    )
    DB_UNAVAILABLE = ErrorDefinition(
        "DB_UNAVAILABLE",
        "Database unavailable",
        status.HTTP_503_SERVICE_UNAVAILABLE,
    )
    LOCK_TIMEOUT = ErrorDefinition(
        "LOCK_TIMEOUT",
        "Lock wait timeout",
        status.HTTP_409_CONFLICT,
    )
    VALIDATION_ERROR = ErrorDefinition(
        "VALIDATION_ERROR",
        "Validation error",
        status.HTTP_422_UNPROCESSABLE_ENTITY,
    )
    INTERNAL_ERROR = ErrorDefinition(
        "INTERNAL_ERROR",
        "Internal server error",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
    IDEMPOTENCY_KEY_REQUIRED = ErrorDefinition(
        "IDEMPOTENCY_KEY_REQUIRED",
        "Idempotency key required",
        status.HTTP_400_BAD_REQUEST,
    )
    IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD = ErrorDefinition(
        "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD",
        "Idempotency key reused with different payload",
        status.HTTP_409_CONFLICT,
    )
    IDEMPOTENCY_REQUEST_IN_PROGRESS = ErrorDefinition(
        "IDEMPOTENCY_REQUEST_IN_PROGRESS",
        "Idempotency request already in progress",
        status.HTTP_409_CONFLICT,
    )
    IDEMPOTENCY_REPLAY = ErrorDefinition(
        "IDEMPOTENCY_REPLAY",
        "Idempotent replay",
        status.HTTP_200_OK,
    )


class AppError(Exception):
    def __init__(self, error: ErrorDefinition, details: object | None = None):
        self.error = error
        self.details = details
        super().__init__(error.message)
