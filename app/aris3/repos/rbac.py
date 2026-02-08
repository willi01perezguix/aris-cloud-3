from sqlalchemy import select

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
