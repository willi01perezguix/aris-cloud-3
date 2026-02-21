from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.aris3.schemas.errors import ApiErrorResponse, ApiValidationErrorResponse


AdminRole = Literal["USER", "MANAGER", "ADMIN"]
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


class StoreListResponse(BaseModel):
    stores: list[StoreItem]
    trace_id: str


class TenantCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class TenantUpdateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class TenantActionRequest(BaseModel):
    action: Literal["set_status"]
    status: AdminUserStatus | None = None


class TenantItem(BaseModel):
    id: str
    name: str
    status: str = Field(..., json_schema_extra={"enum": ["ACTIVE", "SUSPENDED", "CANCELED", "active", "suspended", "canceled"]})
    created_at: datetime


class TenantResponse(BaseModel):
    tenant: TenantItem
    trace_id: str


class TenantListResponse(BaseModel):
    tenants: list[TenantItem]
    trace_id: str


class TenantActionResponse(BaseModel):
    tenant: TenantItem
    action: str
    trace_id: str


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=150)
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=255)
    role: AdminRole = "USER"
    store_id: str | None = None


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
    role: str = Field(..., json_schema_extra={"enum": ["USER", "MANAGER", "ADMIN"]})
    status: str = Field(..., json_schema_extra={"enum": ["ACTIVE", "SUSPENDED", "CANCELED", "active", "suspended", "canceled"]})
    is_active: bool
    must_change_password: bool
    created_at: datetime


class UserResponse(BaseModel):
    user: UserItem
    trace_id: str


class UserListResponse(BaseModel):
    users: list[UserItem]
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
    transaction_id: str | None = Field(None, min_length=1, max_length=255)


class UserActionResponse(BaseModel):
    user: UserItem
    action: AdminUserAction
    temporary_password: str | None = None
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
    """Partial update payload. Only provided fields are modified."""

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
    non_reusable_label_strategy: Literal["ASSIGN_NEW_EPC", "TO_PENDING"]
    restocking_fee_pct: float
    trace_id: str


class ReturnPolicySettingsPatchRequest(BaseModel):
    """Partial update payload. Only provided fields are modified."""

    return_window_days: int | None = Field(None, ge=0)
    require_receipt: bool | None = None
    allow_refund_cash: bool | None = None
    allow_refund_card: bool | None = None
    allow_refund_transfer: bool | None = None
    allow_exchange: bool | None = None
    require_manager_for_exceptions: bool | None = None
    accepted_conditions: list[str] | None = None
    non_reusable_label_strategy: Literal["ASSIGN_NEW_EPC", "TO_PENDING"] | None = None
    restocking_fee_pct: float | None = Field(None, ge=0)
