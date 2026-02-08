from sqlalchemy import select

from app.aris3.db.models import IdempotencyRecord


class IdempotencyRepository:
    def __init__(self, db):
        self.db = db

    def get_by_key(self, *, tenant_id: str, endpoint: str, method: str, idempotency_key: str):
        stmt = select(IdempotencyRecord).where(
            IdempotencyRecord.tenant_id == tenant_id,
            IdempotencyRecord.endpoint == endpoint,
            IdempotencyRecord.method == method,
            IdempotencyRecord.idempotency_key == idempotency_key,
        )
        return self.db.execute(stmt).scalars().first()

    def create(self, record: IdempotencyRecord) -> IdempotencyRecord:
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def update(self, record: IdempotencyRecord) -> IdempotencyRecord:
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record
