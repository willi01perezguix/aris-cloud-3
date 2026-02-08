from sqlalchemy import delete, select

from app.aris3.db.models import PermissionCatalog, RoleTemplate, RoleTemplatePermission


class RoleTemplateRepository:
    def __init__(self, db):
        self.db = db

    def get_role_template(self, role_name: str, tenant_id: str | None = None):
        stmt = select(RoleTemplate).where(RoleTemplate.name == role_name)
        if tenant_id is None:
            stmt = stmt.where(RoleTemplate.tenant_id.is_(None))
        else:
            stmt = stmt.where(RoleTemplate.tenant_id == tenant_id)
        return self.db.execute(stmt).scalars().first()

    def list_permissions_for_role(self, role_name: str, tenant_id: str | None = None):
        stmt = (
            select(PermissionCatalog.code)
            .join(RoleTemplatePermission, RoleTemplatePermission.permission_id == PermissionCatalog.id)
            .join(RoleTemplate, RoleTemplatePermission.role_template_id == RoleTemplate.id)
            .where(RoleTemplate.name == role_name)
        )
        if tenant_id is None:
            stmt = stmt.where(RoleTemplate.tenant_id.is_(None))
        else:
            stmt = stmt.where(RoleTemplate.tenant_id == tenant_id)
        return [row[0] for row in self.db.execute(stmt).all()]

    def list_permissions_for_role_template(self, role_template_id):
        stmt = (
            select(PermissionCatalog.code)
            .join(RoleTemplatePermission, RoleTemplatePermission.permission_id == PermissionCatalog.id)
            .where(RoleTemplatePermission.role_template_id == role_template_id)
        )
        return [row[0] for row in self.db.execute(stmt).all()]

    def list_permission_catalog(self):
        stmt = select(PermissionCatalog).order_by(PermissionCatalog.code)
        return self.db.execute(stmt).scalars().all()

    def replace_role_template_permissions(self, role_template_id, permission_codes: list[str]) -> None:
        stmt = delete(RoleTemplatePermission).where(
            RoleTemplatePermission.role_template_id == role_template_id
        )
        self.db.execute(stmt)
        if not permission_codes:
            return
        permissions = (
            self.db.execute(
                select(PermissionCatalog).where(PermissionCatalog.code.in_(permission_codes))
            )
            .scalars()
            .all()
        )
        permission_map = {perm.code: perm for perm in permissions}
        for code in sorted(set(permission_codes)):
            permission = permission_map.get(code)
            if not permission:
                continue
            self.db.add(
                RoleTemplatePermission(role_template_id=role_template_id, permission_id=permission.id)
            )
