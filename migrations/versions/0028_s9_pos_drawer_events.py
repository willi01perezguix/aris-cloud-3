"""s9 pos drawer events

Revision ID: 0028_s9_pos_drawer_events
Revises: 0027_s9_pos_schema_drift_repair
Create Date: 2026-04-14 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0028_s9_pos_drawer_events"
down_revision = "0027_s9_pos_schema_drift_repair"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "drawer_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("store_id", sa.String(length=36), nullable=False),
        sa.Column("terminal_id", sa.String(length=100), nullable=True),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("cash_session_id", sa.String(length=36), nullable=True),
        sa.Column("sale_id", sa.String(length=36), nullable=True),
        sa.Column("movement_type", sa.String(length=30), nullable=False),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("printer_name", sa.String(length=255), nullable=True),
        sa.Column("machine_name", sa.String(length=255), nullable=True),
        sa.Column("requested_at", sa.DateTime(), nullable=True),
        sa.Column("executed_at", sa.DateTime(), nullable=True),
        sa.Column("closed_confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("result", sa.String(length=20), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_drawer_events_tenant_id", "drawer_events", ["tenant_id"], unique=False)
    op.create_index("ix_drawer_events_store_id", "drawer_events", ["store_id"], unique=False)
    op.create_index("ix_drawer_events_user_id", "drawer_events", ["user_id"], unique=False)
    op.create_index("ix_drawer_events_cash_session_id", "drawer_events", ["cash_session_id"], unique=False)
    op.create_index("ix_drawer_events_sale_id", "drawer_events", ["sale_id"], unique=False)
    op.create_index("ix_drawer_events_tenant_store_created", "drawer_events", ["tenant_id", "store_id", "created_at"], unique=False)
    op.create_index("ix_drawer_events_cash_session_created", "drawer_events", ["cash_session_id", "created_at"], unique=False)
    op.create_index("ix_drawer_events_sale_created", "drawer_events", ["sale_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_drawer_events_sale_created", table_name="drawer_events")
    op.drop_index("ix_drawer_events_cash_session_created", table_name="drawer_events")
    op.drop_index("ix_drawer_events_tenant_store_created", table_name="drawer_events")
    op.drop_index("ix_drawer_events_sale_id", table_name="drawer_events")
    op.drop_index("ix_drawer_events_cash_session_id", table_name="drawer_events")
    op.drop_index("ix_drawer_events_user_id", table_name="drawer_events")
    op.drop_index("ix_drawer_events_store_id", table_name="drawer_events")
    op.drop_index("ix_drawer_events_tenant_id", table_name="drawer_events")
    op.drop_table("drawer_events")
