from app.aris3.repos.rbac import RoleTemplateRepository


class RBACService:
    def __init__(self, db):
        self.repo = RoleTemplateRepository(db)

    def get_permissions_for_role(self, role_name: str, tenant_id: str | None = None):
        return self.repo.list_permissions_for_role(role_name, tenant_id)
