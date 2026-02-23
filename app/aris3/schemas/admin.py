from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.aris3.schemas.errors import ApiErrorResponse, ApiValidationErrorResponse


AdminRole = Literal["USER", "MANAGER", "ADMIN"]
AdminUserRole = Literal["USER", "MANAGER", "ADMIN", "SUPERADMIN", "PLATFORM_ADMIN"]
AdminUserStatus = Literal["ACTIVE", "SUSPENDED", "CANCELED", "active", "suspended", "canceled"]
AdminUserAction = Literal["set_status", "set_role", "reset_password"]


class StoreCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    tenant_id: str | None = Field(
        default=None,
        description=(
            "Canonical tenant for store creation. Superadmin/platform admin must provide this field "
            "(or legacy query_tenant_id); no implicit fallback to token default tenant is applied."
        ),
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"name": "Store Centro", "tenant_id": "4f7f2c5e-9cfd-4efa-a575-2a0ad38df4e8"},
                {"name": "Store Centro"},
            ]
        }
    }


class StoreUpdateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class StoreItem(BaseModel):
    id: str
    tenant_id: str
    name: str
    created_at: datetime


class StoreResponse(BaseModel):
    store: StoreItem
    trace_id: str


class ListPaginationMeta(BaseModel):
    total: int
    count: int
    limit: int
    offset: int


class StoreListResponse(BaseModel):
    stores: list[StoreItem]
    pagination: ListPaginationMeta | None = None
    trace_id: str


class TenantCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class TenantUpdateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class TenantActionRequest(BaseModel):
    action: Literal["set_status"]
    status: AdminUserStatus | None = Field(
        default=None,
        description="Required when `action=set_status`.",
    )


class TenantItem(BaseModel):
    id: str
    name: str
    status: AdminUserStatus = Field(..., description="Current tenant status.")
    created_at: datetime


class TenantResponse(BaseModel):
    tenant: TenantItem
    trace_id: str


class TenantListResponse(BaseModel):
    tenants: list[TenantItem]
    pagination: ListPaginationMeta | None = None
    trace_id: str


class TenantActionResponse(BaseModel):
    tenant: TenantItem
    action: Literal["set_status"]
    trace_id: str


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=150)
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=255)
    role: AdminRole = "USER"
    store_id: str = Field(..., min_length=1)
    tenant_id: str | None = Field(
        default=None,
        description="Deprecated: tenant scope is derived from store_id on the backend.",
    )


class UserUpdateRequest(BaseModel):
    username: str | None = Field(None, min_length=1, max_length=150)
    email: str | None = Field(None, min_length=3, max_length=255)
    store_id: str | None = None


class UserItem(BaseModel):
    id: str
    tenant_id: str
    store_id: str | None
    username: str
    email: str
    role: AdminUserRole = Field(..., description="Resolved user role as persisted in runtime.")
    status: AdminUserStatus = Field(..., description="Runtime user status.")
    is_active: bool
    must_change_password: bool
    created_at: datetime


class UserResponse(BaseModel):
    user: UserItem
    trace_id: str


class UserListResponse(BaseModel):
    users: list[UserItem]
    pagination: ListPaginationMeta | None = None
    trace_id: str


class UserActionRequest(BaseModel):
    action: AdminUserAction = Field(
        ...,
        description="Action to execute. `set_status` uses `status`, `set_role` uses `role`, and `reset_password` optionally uses `temporary_password`.",
    )
    status: AdminUserStatus | None = Field(
        default=None,
        description="Required only when `action=set_status`.",
    )
    role: AdminRole | None = Field(
        default=None,
        description="Required only when `action=set_role`.",
    )
    temporary_password: str | None = Field(
        default=None,
        description="Optional only when `action=reset_password`. If omitted, server generates a temporary password.",
    )
    transaction_id: str | None = Field(
        None,
        min_length=1,
        max_length=255,
        description="Required for all actions to correlate idempotency and audit events.",
    )


class SetUserStatusActionRequest(BaseModel):
    action: Literal["set_status"]
    status: AdminUserStatus = Field(..., description="Target status.")
    role: None = Field(default=None, description="Must be omitted for this action.")
    temporary_password: None = Field(default=None, description="Must be omitted for this action.")
    transaction_id: str = Field(..., min_length=1, max_length=255)


class SetUserRoleActionRequest(BaseModel):
    action: Literal["set_role"]
    status: None = Field(default=None, description="Must be omitted for this action.")
    role: AdminRole = Field(..., description="Target role allowed by policy checks.")
    temporary_password: None = Field(default=None, description="Must be omitted for this action.")
    transaction_id: str = Field(..., min_length=1, max_length=255)


class ResetUserPasswordActionRequest(BaseModel):
    action: Literal["reset_password"]
    status: None = Field(default=None, description="Must be omitted for this action.")
    role: None = Field(default=None, description="Must be omitted for this action.")
    temporary_password: str | None = Field(
        default=None,
        description="Optional temporary password. If omitted, server generates one.",
    )
    transaction_id: str = Field(..., min_length=1, max_length=255)


class UserActionResponse(BaseModel):
    user: UserItem
    action: AdminUserAction
    temporary_password: str | None = Field(
        default=None,
        description="Present only when `action=reset_password`; otherwise null.",
    )
    trace_id: str


class SetUserStatusActionResponse(BaseModel):
    user: UserItem
    action: Literal["set_status"]
    temporary_password: None = None
    trace_id: str


class SetUserRoleActionResponse(BaseModel):
    user: UserItem
    action: Literal["set_role"]
    temporary_password: None = None
    trace_id: str


class ResetUserPasswordActionResponse(BaseModel):
    user: UserItem
    action: Literal["reset_password"]
    temporary_password: str
    trace_id: str


class AdminDeleteResponse(BaseModel):
    resource: Literal["tenant", "store", "user"]
    resource_id: str
    deleted: bool = True
    trace_id: str


class AdminDeleteConflictResponse(ApiErrorResponse):
    details: dict | None = None


class AdminErrorResponse(ApiErrorResponse):
    pass


class AdminValidationErrorResponse(ApiValidationErrorResponse):
    pass


class VariantFieldSettingsResponse(BaseModel):
    var1_label: str | None
    var2_label: str | None
    trace_id: str


class VariantFieldSettingsPatchRequest(BaseModel):
    """Partial update payload. Omitted fields remain unchanged."""

    var1_label: str | None = Field(None, max_length=255)
    var2_label: str | None = Field(None, max_length=255)


class ReturnPolicySettingsResponse(BaseModel):
    return_window_days: int
    require_receipt: bool
    allow_refund_cash: bool
    allow_refund_card: bool
    allow_refund_transfer: bool
    allow_exchange: bool
    require_manager_for_exceptions: bool
    accepted_conditions: list[str]
    non_reusable_label_strategy: Literal["ASSIGN_NEW_EPC", "TO_PENDING"] = Field(
        ...,
        description=(
            "Strategy for non-reusable labels during returns: `ASSIGN_NEW_EPC` assigns a fresh EPC, "
            "`TO_PENDING` moves the label to pending flow."
        ),
    )
    restocking_fee_pct: float
    trace_id: str


class ReturnPolicySettingsPatchRequest(BaseModel):
    """Partial update payload. Omitted fields remain unchanged."""

    return_window_days: int | None = Field(None, ge=0)
    require_receipt: bool | None = None
    allow_refund_cash: bool | None = None
    allow_refund_card: bool | None = None
    allow_refund_transfer: bool | None = None
    allow_exchange: bool | None = None
    require_manager_for_exceptions: bool | None = None
    accepted_conditions: list[str] | None = None
    non_reusable_label_strategy: Literal["ASSIGN_NEW_EPC", "TO_PENDING"] | None = Field(
        default=None,
        description="Optional partial update for non-reusable label handling strategy.",
    )
    restocking_fee_pct: float | None = Field(None, ge=0)
