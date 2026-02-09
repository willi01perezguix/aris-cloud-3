from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from app.aris3.db.models import PosPayment, PosSale, PosSaleLine


@dataclass(frozen=True)
class PosSaleQueryFilters:
    tenant_id: str
    store_id: str | None = None


class PosSaleRepository:
    def __init__(self, db):
        self.db = db

    def list_sales(self, filters: PosSaleQueryFilters) -> list[PosSale]:
        query = select(PosSale).where(PosSale.tenant_id == filters.tenant_id)
        if filters.store_id:
            query = query.where(PosSale.store_id == filters.store_id)
        return self.db.execute(query.order_by(PosSale.created_at.desc())).scalars().all()

    def get_by_id(self, sale_id: str) -> PosSale | None:
        return self.db.execute(select(PosSale).where(PosSale.id == sale_id)).scalars().first()

    def get_lines(self, sale_id: str) -> list[PosSaleLine]:
        return (
            self.db.execute(select(PosSaleLine).where(PosSaleLine.sale_id == sale_id).order_by(PosSaleLine.created_at))
            .scalars()
            .all()
        )

    def get_payments(self, sale_id: str) -> list[PosPayment]:
        return (
            self.db.execute(select(PosPayment).where(PosPayment.sale_id == sale_id).order_by(PosPayment.created_at))
            .scalars()
            .all()
        )
