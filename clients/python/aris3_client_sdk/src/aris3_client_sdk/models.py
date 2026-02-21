from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    access_token: str
    must_change_password: bool = False
    trace_id: str | None = None


class UserResponse(BaseModel):
    id: str
    username: str
    email: str | None = None
    tenant_id: str | None = None
    store_id: str | None = None
    role: str | None = None
    status: str | None = None
    is_active: bool | None = None
    must_change_password: bool | None = None
    trace_id: str | None = None


class TenantStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELED = "canceled"


class UserStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELED = "canceled"


class UserRole(str, Enum):
    USER = "USER"
    MANAGER = "MANAGER"
    ADMIN = "ADMIN"
    SUPERADMIN = "SUPERADMIN"
    PLATFORM_ADMIN = "PLATFORM_ADMIN"


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class PaginationMeta(BaseModel):
    total: int
    count: int
    limit: int
    offset: int


class TenantItem(BaseModel):
    id: str
    name: str
    status: str
    created_at: str | None = None


class StoreItem(BaseModel):
    id: str
    tenant_id: str
    name: str
    created_at: str | None = None


class UserItem(BaseModel):
    id: str
    tenant_id: str
    store_id: str | None = None
    username: str
    email: str | None = None
    role: str | None = None
    status: str | None = None
    is_active: bool | None = None
    must_change_password: bool | None = None
    created_at: str | None = None


class TenantListResponse(BaseModel):
    tenants: List[TenantItem] = Field(default_factory=list)
    trace_id: str | None = None
    pagination: PaginationMeta | None = None


class StoreListResponse(BaseModel):
    stores: List[StoreItem] = Field(default_factory=list)
    trace_id: str | None = None
    pagination: PaginationMeta | None = None


class UserListResponse(BaseModel):
    users: List[UserItem] = Field(default_factory=list)
    trace_id: str | None = None
    pagination: PaginationMeta | None = None


class PermissionEntry(BaseModel):
    key: str
    allowed: bool
    source: str | None = None


class EffectivePermissionSubject(BaseModel):
    user_id: str | None = None
    tenant_id: str | None = None
    store_id: str | None = None
    role: str | None = None


class PermissionSourceTrace(BaseModel):
    allow: List[str] = Field(default_factory=list)
    deny: List[str] = Field(default_factory=list)


class EffectivePermissionsTrace(BaseModel):
    template: PermissionSourceTrace
    tenant: PermissionSourceTrace
    store: PermissionSourceTrace
    user: PermissionSourceTrace


class EffectivePermissionsResponse(BaseModel):
    user_id: str
    tenant_id: str | None = None
    store_id: str | None = None
    role: str | None = None
    permissions: List[PermissionEntry]
    subject: EffectivePermissionSubject
    denies_applied: List[str] = Field(default_factory=list)
    sources_trace: EffectivePermissionsTrace
    trace_id: str | None = None


class SessionData(BaseModel):
    access_token: str
    user: Optional[UserResponse] = None
    env_name: str | None = None
