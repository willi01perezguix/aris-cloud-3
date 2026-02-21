from typing import Literal

from pydantic import BaseModel, Field


AccessControlRole = Literal["USER", "MANAGER", "ADMIN", "SUPERADMIN", "PLATFORM_ADMIN"]
PermissionSource = Literal[
    "role_template",
    "tenant_policy_allow",
    "tenant_policy_deny",
    "store_policy_allow",
    "store_policy_deny",
    "user_override_allow",
    "user_override_deny",
    "explicit_deny",
    "default_deny",
    "unknown_permission",
]


class PermissionCatalogItem(BaseModel):
    code: str = Field(..., description="Permission code consumed by frontend/SDK (for example `inventory.read`).")
    description: str | None = Field(default=None, description="Human-friendly permission description.")


class ReplacePolicyRequest(BaseModel):
    allow: list[str] = Field(default_factory=list, description="Permissions explicitly allowed in this layer.")
    deny: list[str] = Field(default_factory=list, description="Permissions explicitly denied in this layer.")
    transaction_id: str | None = Field(None, min_length=1, max_length=255)


class PatchOverridesRequest(BaseModel):
    allow: list[str] | None = Field(default=None, description="Replace allow overrides when provided.")
    deny: list[str] | None = Field(default=None, description="Replace deny overrides when provided.")
    transaction_id: str | None = Field(None, min_length=1, max_length=255)


class EffectivePermissionItem(BaseModel):
    key: str = Field(..., description="Permission code.")
    allowed: bool = Field(..., description="Resolved permission decision after applying all policy layers.")
    source: PermissionSource = Field(..., description="Layer that produced the final decision for this permission.")


class PermissionSubject(BaseModel):
    user_id: str = Field(..., description="Resolved user identifier for this computation.")
    tenant_id: str | None = Field(default=None, description="Resolved tenant scope used for policy resolution.")
    store_id: str | None = Field(default=None, description="Resolved store scope used for policy resolution.")
    role: AccessControlRole | None = Field(default=None, description="Resolved role used as template baseline.")


class PolicyLayerTrace(BaseModel):
    allow: list[str] = Field(default_factory=list, description="Permissions contributed as allow by this layer.")
    deny: list[str] = Field(default_factory=list, description="Permissions contributed as deny by this layer.")


class EffectivePermissionsTrace(BaseModel):
    template: PolicyLayerTrace = Field(..., description="Role Template layer (base permissions per role).")
    tenant: PolicyLayerTrace = Field(..., description="Tenant Role Policy overlay for the resolved role.")
    store: PolicyLayerTrace = Field(..., description="Store Role Policy overlay for the resolved role/store.")
    user: PolicyLayerTrace = Field(..., description="User overrides layer (final explicit allow/deny adjustments).")


class EffectivePermissionsResponse(BaseModel):
    user_id: str = Field(..., description="Top-level legacy summary: mirrors `subject.user_id`.")
    tenant_id: str | None = Field(default=None, description="Top-level legacy summary: mirrors `subject.tenant_id`.")
    store_id: str | None = Field(default=None, description="Top-level legacy summary: mirrors `subject.store_id`.")
    role: AccessControlRole | None = Field(default=None, description="Top-level legacy summary: mirrors `subject.role`.")
    permissions: list[EffectivePermissionItem]
    subject: PermissionSubject = Field(..., description="Canonical subject context used by effective permission resolution.")
    denies_applied: list[str] = Field(
        default_factory=list,
        description="Flattened list of permission codes that ended as deny after precedence resolution.",
    )
    sources_trace: EffectivePermissionsTrace = Field(
        ...,
        description="Trace of allow/deny contributions by policy layer.",
    )
    trace_id: str


class PermissionCatalogResponse(BaseModel):
    permissions: list[PermissionCatalogItem]
    trace_id: str


class RolePolicyResponse(BaseModel):
    tenant_id: str | None
    role: AccessControlRole = Field(..., description="Role whose policy was resolved for this scope.")
    allow: list[str]
    deny: list[str]
    trace_id: str


class StoreRolePolicyResponse(BaseModel):
    tenant_id: str
    store_id: str
    role: AccessControlRole = Field(..., description="Role whose policy was resolved for this store scope.")
    allow: list[str]
    deny: list[str]
    trace_id: str


class UserOverridesResponse(BaseModel):
    tenant_id: str
    user_id: str
    allow: list[str]
    deny: list[str]
    trace_id: str


class RoleTemplateResponse(BaseModel):
    role: AccessControlRole = Field(..., description="Role template baseline.")
    permissions: list[str]
    trace_id: str


# Backwards-compatible aliases used by routers.
PermissionEntry = EffectivePermissionItem
EffectivePermissionSubject = PermissionSubject
PermissionSourceTrace = PolicyLayerTrace
PermissionCatalogEntry = PermissionCatalogItem
RolePolicyRequest = ReplacePolicyRequest
UserPermissionOverrideRequest = ReplacePolicyRequest
UserPermissionOverridePatchRequest = PatchOverridesRequest
UserPermissionOverrideResponse = UserOverridesResponse
class RoleTemplateRequest(BaseModel):
    permissions: list[str] = Field(default_factory=list, description="Template permission set for the role.")
    transaction_id: str | None = Field(None, min_length=1, max_length=255)
