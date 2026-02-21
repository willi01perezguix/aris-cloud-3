from sqlalchemy import func, select

from app.aris3.db.models import Store


class StoreRepository:
    def __init__(self, db):
        self.db = db

    def get_by_id(self, store_id: str):
        return self.db.get(Store, store_id)

    def get_by_id_in_tenant(self, store_id: str, tenant_id: str):
        stmt = select(Store).where(Store.id == store_id, Store.tenant_id == tenant_id)
        return self.db.execute(stmt).scalars().first()

    def list_by_tenant(
        self,
        tenant_id: str,
        *,
        tenant_filter_id: str | None = None,
        search: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        sort_by: str = "name",
        sort_order: str = "asc",
    ):
        effective_tenant_id = tenant_filter_id or tenant_id
        stmt = select(Store).where(Store.tenant_id == effective_tenant_id)
        count_stmt = select(func.count()).select_from(Store).where(Store.tenant_id == effective_tenant_id)

        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(Store.name.ilike(pattern))
            count_stmt = count_stmt.where(Store.name.ilike(pattern))

        sort_column = Store.name if sort_by == "name" else Store.created_at
        stmt = stmt.order_by(sort_column.asc() if sort_order == "asc" else sort_column.desc())

        if offset:
            stmt = stmt.offset(offset)
        if limit:
            stmt = stmt.limit(limit)

        rows = self.db.execute(stmt).scalars().all()
        total = self.db.execute(count_stmt).scalar_one()
        return rows, total

    def create(self, store: Store):
        self.db.add(store)
        self.db.commit()
        self.db.refresh(store)
        return store

    def update(self, store: Store):
        self.db.add(store)
        self.db.commit()
        self.db.refresh(store)
        return store
