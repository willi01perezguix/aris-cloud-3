from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select

from app.aris3.db.models import PosAdvance, PosAdvanceEvent


TERMINAL_STATUSES = {"CONSUMED", "REFUNDED", "EXPIRED"}


def expire_advance_if_needed(db, advance: PosAdvance, *, actor_user_id: str | None = None, now: datetime | None = None) -> bool:
    now = now or datetime.utcnow()
    if advance.status == "ACTIVE" and advance.expires_at <= now:
        advance.status = "EXPIRED"
        advance.expired_at = now
        advance.updated_at = now
        db.add(
            PosAdvanceEvent(
                advance_id=advance.id,
                tenant_id=advance.tenant_id,
                store_id=advance.store_id,
                action="EXPIRED",
                payload={"reason": "lazy_expiration", "expired_at": now.isoformat() + "Z"},
                created_by_user_id=UUID(actor_user_id) if actor_user_id else None,
                created_at=now,
            )
        )
        return True
    return False


def sweep_expired_advances(
    db,
    *,
    tenant_id,
    store_id,
    actor_user_id: str | None = None,
    now: datetime | None = None,
) -> list[PosAdvance]:
    now = now or datetime.utcnow()
    rows = (
        db.execute(
            select(PosAdvance)
            .where(
                PosAdvance.tenant_id == tenant_id,
                PosAdvance.store_id == store_id,
                PosAdvance.status == "ACTIVE",
                PosAdvance.expires_at <= now,
            )
            .with_for_update()
        )
        .scalars()
        .all()
    )
    for advance in rows:
        expire_advance_if_needed(db, advance, actor_user_id=actor_user_id, now=now)
    return rows
