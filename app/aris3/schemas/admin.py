from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class StoreCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


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
    status: Literal["ACTIVE", "SUSPENDED", "CANCELED"] | None = None


class TenantItem(BaseModel):
    id: str
    name: str
    status: str
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
    role: Literal["USER", "MANAGER", "ADMIN"] = "USER"
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
    role: str
    status: str
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
    action: Literal["set_status", "set_role", "reset_password"]
    status: Literal["ACTIVE", "SUSPENDED", "CANCELED"] | None = None
    role: Literal["USER", "MANAGER", "ADMIN"] | None = None
    temporary_password: str | None = None


class UserActionResponse(BaseModel):
    user: UserItem
    action: str
    temporary_password: str | None = None
    trace_id: str


class VariantFieldSettingsResponse(BaseModel):
    var1_label: str | None
    var2_label: str | None
    trace_id: str


class VariantFieldSettingsPatchRequest(BaseModel):
    var1_label: str | None = Field(None, max_length=255)
    var2_label: str | None = Field(None, max_length=255)
