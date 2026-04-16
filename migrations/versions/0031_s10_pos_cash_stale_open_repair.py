"""s10 pos cash stale open session repair

Revision ID: 0031_s10_pos_cash_stale_open_repair
Revises: 0030_s10_pos_cash_cuts
Create Date: 2026-04-16 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0031_s10_pos_cash_stale_open_repair"
down_revision = "0030_s10_pos_cash_cuts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    sessions = sa.table(
        "pos_cash_sessions",
        sa.column("id", sa.String(length=36)),
        sa.column("tenant_id", sa.String(length=36)),
        sa.column("store_id", sa.String(length=36)),
        sa.column("business_date", sa.Date()),
        sa.column("status", sa.String(length=20)),
        sa.column("closed_at", sa.DateTime()),
    )
    day_closes = sa.table(
        "pos_cash_day_closes",
        sa.column("tenant_id", sa.String(length=36)),
        sa.column("store_id", sa.String(length=36)),
        sa.column("business_date", sa.Date()),
        sa.column("status", sa.String(length=20)),
    )

    stale_exists = sa.exists(
        sa.select(1).where(
            day_closes.c.tenant_id == sessions.c.tenant_id,
            day_closes.c.store_id == sessions.c.store_id,
            day_closes.c.business_date == sessions.c.business_date,
            day_closes.c.status == "CLOSED",
        )
    )

    op.execute(
        sessions.update()
        .where(
            sessions.c.status == "OPEN",
            sessions.c.closed_at.is_(None),
            stale_exists,
        )
        .values(status="CLOSED", closed_at=sa.func.now())
    )


def downgrade() -> None:
    # Data repair migration is intentionally irreversible.
    pass
