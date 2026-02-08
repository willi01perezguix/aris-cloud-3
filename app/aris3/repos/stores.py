from sqlalchemy import select

from app.aris3.db.models import Store


class StoreRepository:
    def __init__(self, db):
        self.db = db

    def get_by_id(self, store_id: str):
        return self.db.get(Store, store_id)

    def list_by_tenant(self, tenant_id: str):
        stmt = select(Store).where(Store.tenant_id == tenant_id).order_by(Store.name)
        return self.db.execute(stmt).scalars().all()

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
