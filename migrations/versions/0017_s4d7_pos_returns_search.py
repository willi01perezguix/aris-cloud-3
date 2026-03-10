"""sprint4 day7 pos returns receipt and search

Revision ID: 0017_s4d7_pos_returns_search
Revises: 0023_s8dx_items_contract_guard
Create Date: 2024-02-20 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0017_s4d7_pos_returns_search"
down_revision = "0023_s8dx_items_contract_guard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pos_sales", sa.Column("receipt_number", sa.String(length=100), nullable=True))
    op.create_index(
        "ix_pos_sales_tenant_store_receipt",
        "pos_sales",
        ["tenant_id", "store_id", "receipt_number"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_pos_sales_tenant_store_receipt", table_name="pos_sales")
    op.drop_column("pos_sales", "receipt_number")
