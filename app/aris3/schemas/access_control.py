from pydantic import BaseModel


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
