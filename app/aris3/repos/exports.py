from __future__ import annotations

from sqlalchemy import select

from app.aris3.db.models import ExportRecord


class ExportRepository:
    def __init__(self, db):
        self.db = db

    def create(self, record: ExportRecord) -> ExportRecord:
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def update(self, record: ExportRecord) -> ExportRecord:
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_by_id(self, export_id: str, tenant_id: str) -> ExportRecord | None:
        return (
            self.db.execute(
                select(ExportRecord).where(
                    ExportRecord.id == export_id,
                    ExportRecord.tenant_id == tenant_id,
                )
            )
            .scalars()
            .first()
        )

    def list_by_tenant(
        self,
        tenant_id: str,
        *,
        store_id: str | None = None,
        limit: int | None = None,
    ) -> list[ExportRecord]:
        stmt = select(ExportRecord).where(ExportRecord.tenant_id == tenant_id)
        if store_id:
            stmt = stmt.where(ExportRecord.store_id == store_id)
        stmt = stmt.order_by(ExportRecord.created_at.desc(), ExportRecord.id)
        if limit:
            stmt = stmt.limit(limit)
        return self.db.execute(stmt).scalars().all()
