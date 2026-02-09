"""sprint3 day2 stock epc unique

Revision ID: 0009_sprint3_day2
Revises: 0008_sprint3_day1
Create Date: 2024-02-07 00:00:00.000000
"""

from alembic import op


revision = "0009_sprint3_day2"
down_revision = "0008_sprint3_day1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("stock_items") as batch_op:
        batch_op.create_unique_constraint(
            "uq_stock_items_tenant_epc",
            ["tenant_id", "epc"],
        )


def downgrade() -> None:
    with op.batch_alter_table("stock_items") as batch_op:
        batch_op.drop_constraint("uq_stock_items_tenant_epc", type_="unique")
