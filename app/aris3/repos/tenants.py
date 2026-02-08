from sqlalchemy import select

from app.aris3.db.models import Tenant


class TenantRepository:
    def __init__(self, db):
        self.db = db

    def list_all(self):
        stmt = select(Tenant).order_by(Tenant.name)
        return self.db.execute(stmt).scalars().all()

    def get_by_id(self, tenant_id: str):
        return self.db.get(Tenant, tenant_id)

    def get_by_name(self, name: str):
        stmt = select(Tenant).where(Tenant.name == name)
        return self.db.execute(stmt).scalars().first()

    def create(self, tenant: Tenant):
        self.db.add(tenant)
        self.db.commit()
        self.db.refresh(tenant)
        return tenant

    def update(self, tenant: Tenant):
        self.db.add(tenant)
        self.db.commit()
        self.db.refresh(tenant)
        return tenant
