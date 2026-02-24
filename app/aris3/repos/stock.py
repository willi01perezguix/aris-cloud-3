from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, or_, select, case

from app.aris3.db.models import StockItem


@dataclass(frozen=True)
class StockQueryFilters:
    tenant_id: str
    q: str | None = None
    description: str | None = None
    var1_value: str | None = None
    var2_value: str | None = None
    sku: str | None = None
    epc: str | None = None
    location_code: str | None = None
    pool: str | None = None
    store_id: str | None = None
    from_date: datetime | None = None
    to_date: datetime | None = None


class StockRepository:
    def __init__(self, db):
        self.db = db

    def list_stock(
        self,
        filters: StockQueryFilters,
        *,
        page: int,
        page_size: int,
        sort_by: str,
        sort_dir: str,
    ) -> tuple[list[StockItem], dict[str, int], str]:
        base_query = self._apply_filters(filters)
        total_rows = self.db.execute(
            select(func.count()).select_from(base_query.subquery())
        ).scalar_one()

        sort_column = self._resolve_sort_column(sort_by)
        resolved_sort_by = sort_column.key or sort_by
        if sort_dir.lower() == "desc":
            sort_column = sort_column.desc()
        else:
            sort_column = sort_column.asc()

        query = base_query.order_by(sort_column).offset((page - 1) * page_size).limit(page_size)
        rows = self.db.execute(query).scalars().all()

        total_rfid, total_pending = self._totals_for_filters(filters)
        totals = {
            "total_rows": total_rows,
            "total_rfid": total_rfid,
            "total_pending": total_pending,
            "total_units": total_rfid + total_pending,
        }
        return rows, totals, resolved_sort_by

    def _apply_filters(self, filters: StockQueryFilters):
        query = select(StockItem).where(StockItem.tenant_id == filters.tenant_id)
        if filters.q:
            like = f"%{filters.q}%"
            query = query.where(
                or_(
                    StockItem.sku.ilike(like),
                    StockItem.description.ilike(like),
                    StockItem.var1_value.ilike(like),
                    StockItem.var2_value.ilike(like),
                    StockItem.epc.ilike(like),
                    StockItem.location_code.ilike(like),
                    StockItem.pool.ilike(like),
                )
            )
        if filters.description:
            query = query.where(StockItem.description.ilike(f"%{filters.description}%"))
        if filters.var1_value:
            query = query.where(StockItem.var1_value == filters.var1_value)
        if filters.var2_value:
            query = query.where(StockItem.var2_value == filters.var2_value)
        if filters.sku:
            query = query.where(StockItem.sku == filters.sku)
        if filters.epc:
            query = query.where(StockItem.epc == filters.epc)
        if filters.location_code:
            query = query.where(StockItem.location_code == filters.location_code)
        if filters.pool:
            query = query.where(StockItem.pool == filters.pool)
        if filters.store_id:
            query = query.where(StockItem.store_id == filters.store_id)
        if filters.from_date:
            query = query.where(StockItem.created_at >= filters.from_date)
        if filters.to_date:
            query = query.where(StockItem.created_at <= filters.to_date)
        return query

    def _totals_for_filters(self, filters: StockQueryFilters) -> tuple[int, int]:
        base_query = self._apply_filters(filters).subquery()
        total_rfid_expr = func.coalesce(
            func.sum(
                case(
                    (base_query.c.location_is_vendible.is_(True) & (base_query.c.status == "RFID"), 1),
                    else_=0,
                )
            ),
            0,
        )
        total_pending_expr = func.coalesce(
            func.sum(
                case(
                    (base_query.c.location_is_vendible.is_(True) & (base_query.c.status == "PENDING"), 1),
                    else_=0,
                )
            ),
            0,
        )
        totals_query = select(total_rfid_expr, total_pending_expr)
        total_rfid, total_pending = self.db.execute(totals_query).one()
        return int(total_rfid or 0), int(total_pending or 0)

    @staticmethod
    def _resolve_sort_column(sort_by: str):
        mapping = {
            "id": StockItem.id,
            "sku": StockItem.sku,
            "description": StockItem.description,
            "var1_value": StockItem.var1_value,
            "var2_value": StockItem.var2_value,
            "epc": StockItem.epc,
            "location_code": StockItem.location_code,
            "pool": StockItem.pool,
            "store_id": StockItem.store_id,
            "status": StockItem.status,
            "cost_price": StockItem.cost_price,
            "suggested_price": StockItem.suggested_price,
            "sale_price": StockItem.sale_price,
            "created_at": StockItem.created_at,
            "updated_at": StockItem.updated_at,
        }
        return mapping.get(sort_by, StockItem.created_at)
