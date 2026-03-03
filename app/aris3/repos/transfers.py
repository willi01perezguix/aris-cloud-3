from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select

from app.aris3.db.models import Transfer, TransferLine, TransferMovement


@dataclass(frozen=True)
class TransferQueryFilters:
    tenant_id: str
    status: str | None = None
    origin_store_id: str | None = None
    destination_store_id: str | None = None
    page: int = 1
    page_size: int = 50
    sort_by: str = "created_at"
    sort_dir: str = "desc"


class TransferRepository:
    def __init__(self, db):
        self.db = db

    def list_transfers(self, filters: TransferQueryFilters) -> tuple[list[Transfer], int]:
        query = select(Transfer).where(Transfer.tenant_id == filters.tenant_id)
        count_query = select(func.count()).select_from(Transfer).where(Transfer.tenant_id == filters.tenant_id)

        if filters.status:
            query = query.where(Transfer.status == filters.status)
            count_query = count_query.where(Transfer.status == filters.status)
        if filters.origin_store_id:
            query = query.where(Transfer.origin_store_id == filters.origin_store_id)
            count_query = count_query.where(Transfer.origin_store_id == filters.origin_store_id)
        if filters.destination_store_id:
            query = query.where(Transfer.destination_store_id == filters.destination_store_id)
            count_query = count_query.where(Transfer.destination_store_id == filters.destination_store_id)

        sort_column = Transfer.created_at if filters.sort_by == "created_at" else Transfer.updated_at
        if filters.sort_dir == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        offset = (max(filters.page, 1) - 1) * max(filters.page_size, 1)
        query = query.offset(offset).limit(max(filters.page_size, 1))

        rows = self.db.execute(query).scalars().all()
        total = int(self.db.execute(count_query).scalar_one() or 0)
        return rows, total

    def get_transfer(self, transfer_id: str, tenant_id: str) -> Transfer | None:
        return (
            self.db.execute(
                select(Transfer).where(Transfer.id == transfer_id, Transfer.tenant_id == tenant_id)
            )
            .scalars()
            .first()
        )

    def get_lines(self, transfer_id: str) -> list[TransferLine]:
        return (
            self.db.execute(select(TransferLine).where(TransferLine.transfer_id == transfer_id))
            .scalars()
            .all()
        )

    def get_movements(self, transfer_id: str) -> list[TransferMovement]:
        return (
            self.db.execute(select(TransferMovement).where(TransferMovement.transfer_id == transfer_id))
            .scalars()
            .all()
        )

    def count_dispatched(self, transfer_id: str) -> tuple[int, int]:
        query = (
            select(func.count(), func.coalesce(func.sum(TransferMovement.qty), 0))
            .where(
                TransferMovement.transfer_id == transfer_id,
                TransferMovement.action == "DISPATCH",
            )
            .select_from(TransferMovement)
        )
        count, qty = self.db.execute(query).one()
        return int(count or 0), int(qty or 0)

    def get_movement_totals(self, transfer_id: str) -> dict[str, dict[str, int]]:
        query = (
            select(
                TransferMovement.transfer_line_id,
                TransferMovement.action,
                func.coalesce(func.sum(TransferMovement.qty), 0),
            )
            .where(TransferMovement.transfer_id == transfer_id)
            .group_by(TransferMovement.transfer_line_id, TransferMovement.action)
        )
        totals: dict[str, dict[str, int]] = {}
        for line_id, action, qty in self.db.execute(query).all():
            line_key = str(line_id)
            totals.setdefault(line_key, {})[action] = int(qty or 0)
        return totals
