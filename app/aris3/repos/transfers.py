from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select

from app.aris3.db.models import Transfer, TransferLine, TransferMovement


@dataclass(frozen=True)
class TransferQueryFilters:
    tenant_id: str


class TransferRepository:
    def __init__(self, db):
        self.db = db

    def list_transfers(self, filters: TransferQueryFilters) -> list[Transfer]:
        query = select(Transfer).where(Transfer.tenant_id == filters.tenant_id)
        return self.db.execute(query.order_by(Transfer.created_at.desc())).scalars().all()

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
