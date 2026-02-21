from sqlalchemy import func, select

from app.aris3.db.models import Tenant


class TenantRepository:
    def __init__(self, db):
        self.db = db

    def list_all(
        self,
        *,
        status: str | None = None,
        search: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        sort_by: str = "name",
        sort_order: str = "asc",
    ):
        stmt = select(Tenant)
        count_stmt = select(func.count()).select_from(Tenant)

        if status:
            normalized_status = status.strip().lower()
            stmt = stmt.where(func.lower(Tenant.status) == normalized_status)
            count_stmt = count_stmt.where(func.lower(Tenant.status) == normalized_status)

        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(Tenant.name.ilike(pattern))
            count_stmt = count_stmt.where(Tenant.name.ilike(pattern))

        sort_column = Tenant.name if sort_by == "name" else Tenant.created_at
        stmt = stmt.order_by(sort_column.asc() if sort_order == "asc" else sort_column.desc())

        if offset:
            stmt = stmt.offset(offset)
        if limit:
            stmt = stmt.limit(limit)

        rows = self.db.execute(stmt).scalars().all()
        total = self.db.execute(count_stmt).scalar_one()
        return rows, total

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
