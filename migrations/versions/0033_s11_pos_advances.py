"""s11 pos advances

Revision ID: 0033_s11_pos_advances
Revises: 0032_s10_pos_cash_cuts_uuid_fix
Create Date: 2026-04-17 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0033_s11_pos_advances"
down_revision = "0032_s10_pos_cash_cuts_uuid_fix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pos_advances",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("store_id", sa.UUID(), nullable=False),
        sa.Column("advance_number", sa.Integer(), nullable=False),
        sa.Column("barcode_value", sa.String(length=100), nullable=False),
        sa.Column("customer_name", sa.String(length=255), nullable=False),
        sa.Column("issued_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("issued_payment_method", sa.String(length=20), nullable=False),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("consumed_sale_id", sa.UUID(), nullable=True),
        sa.Column("refunded_cash_movement_id", sa.UUID(), nullable=True),
        sa.Column("refunded_at", sa.DateTime(), nullable=True),
        sa.Column("expired_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["consumed_sale_id"], ["pos_sales.id"]),
        sa.ForeignKeyConstraint(["refunded_cash_movement_id"], ["pos_cash_movements.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "store_id", "advance_number", name="uq_pos_advances_store_number"),
        sa.UniqueConstraint("tenant_id", "barcode_value", name="uq_pos_advances_barcode"),
    )
    op.create_index("ix_pos_advances_tenant_id", "pos_advances", ["tenant_id"], unique=False)
    op.create_index("ix_pos_advances_store_id", "pos_advances", ["store_id"], unique=False)
    op.create_index("ix_pos_advances_consumed_sale_id", "pos_advances", ["consumed_sale_id"], unique=False)
    op.create_index("ix_pos_advances_refunded_cash_movement_id", "pos_advances", ["refunded_cash_movement_id"], unique=False)
    op.create_index("ix_pos_advances_tenant_store_status_expires", "pos_advances", ["tenant_id", "store_id", "status", "expires_at"], unique=False)

    op.create_table(
        "pos_advance_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("advance_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("store_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["advance_id"], ["pos_advances.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pos_advance_events_advance_id", "pos_advance_events", ["advance_id"], unique=False)
    op.create_index("ix_pos_advance_events_tenant_id", "pos_advance_events", ["tenant_id"], unique=False)
    op.create_index("ix_pos_advance_events_store_id", "pos_advance_events", ["store_id"], unique=False)
    op.create_index("ix_pos_advance_events_advance_created", "pos_advance_events", ["advance_id", "created_at"], unique=False)
    op.create_index("ix_pos_advance_events_tenant_store_created", "pos_advance_events", ["tenant_id", "store_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pos_advance_events_tenant_store_created", table_name="pos_advance_events")
    op.drop_index("ix_pos_advance_events_advance_created", table_name="pos_advance_events")
    op.drop_index("ix_pos_advance_events_store_id", table_name="pos_advance_events")
    op.drop_index("ix_pos_advance_events_tenant_id", table_name="pos_advance_events")
    op.drop_index("ix_pos_advance_events_advance_id", table_name="pos_advance_events")
    op.drop_table("pos_advance_events")

    op.drop_index("ix_pos_advances_tenant_store_status_expires", table_name="pos_advances")
    op.drop_index("ix_pos_advances_refunded_cash_movement_id", table_name="pos_advances")
    op.drop_index("ix_pos_advances_consumed_sale_id", table_name="pos_advances")
    op.drop_index("ix_pos_advances_store_id", table_name="pos_advances")
    op.drop_index("ix_pos_advances_tenant_id", table_name="pos_advances")
    op.drop_table("pos_advances")
