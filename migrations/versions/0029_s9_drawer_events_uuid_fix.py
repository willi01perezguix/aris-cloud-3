"""s9 drawer events uuid type fix

Revision ID: 0029_s9_drawer_events_uuid_fix
Revises: 0028_s9_pos_drawer_events
Create Date: 2026-04-15 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0029_s9_drawer_events_uuid_fix"
down_revision = "0028_s9_pos_drawer_events"
branch_labels = None
depends_on = None


_UUID_COLUMNS = (
    ("id", False),
    ("tenant_id", False),
    ("store_id", False),
    ("user_id", True),
    ("cash_session_id", True),
    ("sale_id", True),
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for column_name, nullable in _UUID_COLUMNS:
        op.alter_column(
            "drawer_events",
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
            "drawer_events",
            column_name,
            existing_type=postgresql.UUID(),
            type_=sa.String(length=36),
            existing_nullable=nullable,
            postgresql_using=f"{column_name}::text",
        )
