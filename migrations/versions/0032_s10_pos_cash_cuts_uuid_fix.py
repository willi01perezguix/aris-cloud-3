"""s10 pos cash cuts uuid type fix

Revision ID: 0032_s10_pos_cash_cuts_uuid_fix
Revises: 0031_s10_pos_cash_stale_open_repair
Create Date: 2026-04-17 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0032_s10_pos_cash_cuts_uuid_fix"
down_revision = "0031_s10_pos_cash_stale_open_repair"
branch_labels = None
depends_on = None


_UUID_COLUMNS = (
    ("id", False),
    ("tenant_id", False),
    ("store_id", False),
    ("cash_session_id", False),
    ("deposit_cash_movement_id", True),
    ("created_by_user_id", False),
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for column_name, nullable in _UUID_COLUMNS:
        op.alter_column(
            "pos_cash_cuts",
            column_name,
            existing_type=sa.String(length=36),
            type_=postgresql.UUID(),
            existing_nullable=nullable,
            postgresql_using=f"{column_name}::uuid",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for column_name, nullable in _UUID_COLUMNS:
        op.alter_column(
            "pos_cash_cuts",
            column_name,
            existing_type=postgresql.UUID(),
            type_=sa.String(length=36),
            existing_nullable=nullable,
            postgresql_using=f"{column_name}::text",
        )
