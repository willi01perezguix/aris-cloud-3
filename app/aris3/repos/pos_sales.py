from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import String, cast, func, or_, select

from app.aris3.db.models import PosPayment, PosReturnEvent, PosSale, PosSaleLine


@dataclass(frozen=True)
class PosSaleQueryFilters:
    tenant_id: str
    store_id: str | None = None
    receipt_number: str | None = None
    status: str | None = None
    from_date: datetime | None = None
    to_date: datetime | None = None
    q: str | None = None
    sku: str | None = None
    epc: str | None = None
    page: int = 1
    page_size: int = 20


class PosSaleRepository:
    def __init__(self, db):
        self.db = db

    def list_sales(self, filters: PosSaleQueryFilters) -> tuple[list[PosSale], int]:
        query = select(PosSale).where(PosSale.tenant_id == filters.tenant_id)
        if filters.store_id:
            query = query.where(PosSale.store_id == filters.store_id)
        if filters.receipt_number:
            query = query.where(PosSale.receipt_number == filters.receipt_number)
        if filters.status:
            query = query.where(func.upper(PosSale.status) == filters.status.upper())
        if filters.from_date:
            query = query.where(PosSale.created_at >= filters.from_date)
        if filters.to_date:
            query = query.where(PosSale.created_at <= filters.to_date)
        if filters.sku or filters.epc:
            line_query = select(PosSaleLine.sale_id).where(PosSaleLine.tenant_id == filters.tenant_id)
            if filters.sku:
                line_query = line_query.where(PosSaleLine.sku == filters.sku)
            if filters.epc:
                line_query = line_query.where(PosSaleLine.epc == filters.epc)
            query = query.where(PosSale.id.in_(line_query))
        if filters.q:
            term = f"%{filters.q.strip()}%"
            line_query = select(PosSaleLine.sale_id).where(
                PosSaleLine.tenant_id == filters.tenant_id,
                or_(
                    PosSaleLine.sku.ilike(term),
                    PosSaleLine.epc.ilike(term),
                    PosSaleLine.description.ilike(term),
                ),
            )
            query = query.where(
                or_(
                    cast(PosSale.id, String).ilike(term),
                    PosSale.receipt_number.ilike(term),
                    PosSale.status.ilike(term),
                    PosSale.id.in_(line_query),
                )
            )

        count_query = select(func.count()).select_from(query.subquery())
        total = int(self.db.execute(count_query).scalar_one())
        offset = max(filters.page - 1, 0) * filters.page_size
        rows = self.db.execute(query.order_by(PosSale.created_at.desc()).offset(offset).limit(filters.page_size)).scalars().all()
        return rows, total

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

    def get_return_events(self, sale_id: str) -> list[PosReturnEvent]:
        return (
            self.db.execute(select(PosReturnEvent).where(PosReturnEvent.sale_id == sale_id).order_by(PosReturnEvent.created_at))
            .scalars()
            .all()
        )
