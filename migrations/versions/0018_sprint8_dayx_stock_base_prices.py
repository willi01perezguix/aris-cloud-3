"""add base prices to stock items

Revision ID: 0018_s8dx_stock_base_prices
Revises: 0017_s4d6_tenant_store_user_hard
Create Date: 2026-02-24 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0018_s8dx_stock_base_prices"
down_revision = "0017_s4d6_tenant_store_user_hard"
branch_labels = None
depends_on = None


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = _column_names(inspector, "stock_items")

    with op.batch_alter_table("stock_items") as batch_op:
        if "cost_price" not in columns:
            batch_op.add_column(sa.Column("cost_price", sa.Numeric(12, 2), nullable=True))
        if "suggested_price" not in columns:
            batch_op.add_column(sa.Column("suggested_price", sa.Numeric(12, 2), nullable=True))
        if "sale_price" not in columns:
            batch_op.add_column(sa.Column("sale_price", sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = _column_names(inspector, "stock_items")

    with op.batch_alter_table("stock_items") as batch_op:
        if "sale_price" in columns:
            batch_op.drop_column("sale_price")
        if "suggested_price" in columns:
            batch_op.drop_column("suggested_price")
        if "cost_price" in columns:
            batch_op.drop_column("cost_price")
