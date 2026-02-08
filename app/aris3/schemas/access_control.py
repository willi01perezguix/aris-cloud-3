from pydantic import BaseModel, Field


class PermissionEntry(BaseModel):
    key: str
    allowed: bool
    source: str


class EffectivePermissionsResponse(BaseModel):
    user_id: str
    tenant_id: str | None
    store_id: str | None
    role: str | None
    permissions: list[PermissionEntry]
    trace_id: str


class PermissionCatalogEntry(BaseModel):
    code: str
    description: str | None


class PermissionCatalogResponse(BaseModel):
    permissions: list[PermissionCatalogEntry]
    trace_id: str


class RolePolicyRequest(BaseModel):
    allow: list[str] = Field(default_factory=list)
    deny: list[str] = Field(default_factory=list)


class RolePolicyResponse(BaseModel):
    tenant_id: str | None
    role: str
    allow: list[str]
    deny: list[str]
    trace_id: str


class StoreRolePolicyResponse(BaseModel):
    tenant_id: str
    store_id: str
    role: str
    allow: list[str]
    deny: list[str]
    trace_id: str


class UserPermissionOverrideRequest(BaseModel):
    allow: list[str] = Field(default_factory=list)
    deny: list[str] = Field(default_factory=list)


class UserPermissionOverrideResponse(BaseModel):
    tenant_id: str
    user_id: str
    allow: list[str]
    deny: list[str]
    trace_id: str
