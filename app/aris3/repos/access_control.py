from sqlalchemy import delete, select

from app.aris3.db.models import (
    PermissionCatalog,
    StoreRolePolicy,
    TenantRolePolicy,
    UserPermissionOverride,
)


class AccessControlPolicyRepository:
    def __init__(self, db):
        self.db = db

    def list_permission_catalog(self):
        stmt = select(PermissionCatalog).order_by(PermissionCatalog.code)
        return self.db.execute(stmt).scalars().all()

    def list_tenant_role_policies(self, *, tenant_id: str | None, role_name: str):
        stmt = select(TenantRolePolicy).where(TenantRolePolicy.role_name == role_name)
        if tenant_id is None:
            stmt = stmt.where(TenantRolePolicy.tenant_id.is_(None))
        else:
            stmt = stmt.where(TenantRolePolicy.tenant_id == tenant_id)
        return self.db.execute(stmt).scalars().all()

    def list_store_role_policies(self, *, tenant_id: str, store_id: str, role_name: str):
        stmt = (
            select(StoreRolePolicy)
            .where(StoreRolePolicy.role_name == role_name)
            .where(StoreRolePolicy.tenant_id == tenant_id)
            .where(StoreRolePolicy.store_id == store_id)
        )
        return self.db.execute(stmt).scalars().all()

    def replace_tenant_role_policies(
        self,
        *,
        tenant_id: str | None,
        role_name: str,
        entries: list[TenantRolePolicy],
    ):
        stmt = delete(TenantRolePolicy).where(TenantRolePolicy.role_name == role_name)
        if tenant_id is None:
            stmt = stmt.where(TenantRolePolicy.tenant_id.is_(None))
        else:
            stmt = stmt.where(TenantRolePolicy.tenant_id == tenant_id)
        self.db.execute(stmt)
        for entry in entries:
            self.db.add(entry)

    def replace_store_role_policies(
        self,
        *,
        tenant_id: str,
        store_id: str,
        role_name: str,
        entries: list[StoreRolePolicy],
    ):
        stmt = delete(StoreRolePolicy).where(StoreRolePolicy.role_name == role_name)
        stmt = stmt.where(StoreRolePolicy.tenant_id == tenant_id).where(StoreRolePolicy.store_id == store_id)
        self.db.execute(stmt)
        for entry in entries:
            self.db.add(entry)

    def list_user_overrides(self, *, tenant_id: str, user_id: str):
        stmt = select(UserPermissionOverride).where(
            UserPermissionOverride.tenant_id == tenant_id,
            UserPermissionOverride.user_id == user_id,
        )
        return self.db.execute(stmt).scalars().all()

    def replace_user_overrides(
        self,
        *,
        tenant_id: str,
        user_id: str,
        entries: list[UserPermissionOverride],
    ):
        stmt = delete(UserPermissionOverride).where(
            UserPermissionOverride.tenant_id == tenant_id,
            UserPermissionOverride.user_id == user_id,
        )
        self.db.execute(stmt)
        for entry in entries:
            self.db.add(entry)
