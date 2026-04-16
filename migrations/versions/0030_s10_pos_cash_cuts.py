"""s10 pos cash cuts

Revision ID: 0030_s10_pos_cash_cuts
Revises: 0029_s9_drawer_events_uuid_fix
Create Date: 2026-04-16 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0030_s10_pos_cash_cuts"
down_revision = "0029_s9_drawer_events_uuid_fix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pos_cash_cuts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("store_id", sa.String(length=36), nullable=False),
        sa.Column("cash_session_id", sa.String(length=36), nullable=False),
        sa.Column("cut_number", sa.Integer(), nullable=False),
        sa.Column("cut_type", sa.String(length=30), nullable=False),
        sa.Column("from_at", sa.DateTime(), nullable=False),
        sa.Column("to_at", sa.DateTime(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("opening_amount_snapshot", sa.Float(), nullable=False),
        sa.Column("cash_sales_total", sa.Float(), nullable=False),
        sa.Column("card_sales_total", sa.Float(), nullable=False),
        sa.Column("transfer_sales_total", sa.Float(), nullable=False),
        sa.Column("mixed_cash_component_total", sa.Float(), nullable=False),
        sa.Column("mixed_card_component_total", sa.Float(), nullable=False),
        sa.Column("mixed_transfer_component_total", sa.Float(), nullable=False),
        sa.Column("cash_in_total", sa.Float(), nullable=False),
        sa.Column("cash_out_total", sa.Float(), nullable=False),
        sa.Column("cash_refunds_total", sa.Float(), nullable=False),
        sa.Column("expected_cash", sa.Float(), nullable=False),
        sa.Column("counted_cash", sa.Float(), nullable=True),
        sa.Column("difference", sa.Float(), nullable=True),
        sa.Column("deposit_removed_amount", sa.Float(), nullable=True),
        sa.Column("deposit_cash_movement_id", sa.String(length=36), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "store_id", "cash_session_id", "cut_number", name="uq_pos_cash_cut_session_number"),
    )
    op.create_index("ix_pos_cash_cuts_tenant_id", "pos_cash_cuts", ["tenant_id"])
    op.create_index("ix_pos_cash_cuts_store_id", "pos_cash_cuts", ["store_id"])
    op.create_index("ix_pos_cash_cuts_cash_session_id", "pos_cash_cuts", ["cash_session_id"])
    op.create_index("ix_pos_cash_cuts_deposit_cash_movement_id", "pos_cash_cuts", ["deposit_cash_movement_id"])
    op.create_index("ix_pos_cash_cuts_tenant_store_to_at", "pos_cash_cuts", ["tenant_id", "store_id", "to_at"])


def downgrade() -> None:
    op.drop_index("ix_pos_cash_cuts_tenant_store_to_at", table_name="pos_cash_cuts")
    op.drop_index("ix_pos_cash_cuts_deposit_cash_movement_id", table_name="pos_cash_cuts")
    op.drop_index("ix_pos_cash_cuts_cash_session_id", table_name="pos_cash_cuts")
    op.drop_index("ix_pos_cash_cuts_store_id", table_name="pos_cash_cuts")
    op.drop_index("ix_pos_cash_cuts_tenant_id", table_name="pos_cash_cuts")
    op.drop_table("pos_cash_cuts")
