"""s12 reports cost snapshot on POS sale lines

Revision ID: 0037_s12_reports_cost_snapshot
Revises: 0036_s12_catalog_products
Create Date: 2026-04-22
"""

from alembic import op
import sqlalchemy as sa


revision = "0037_s12_reports_cost_snapshot"
down_revision = "0036_s12_catalog_products"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(column.get("name") == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _has_column(inspector, "pos_sale_lines", "cost_price_snapshot"):
        with op.batch_alter_table("pos_sale_lines") as batch_op:
            batch_op.add_column(sa.Column("cost_price_snapshot", sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_column(inspector, "pos_sale_lines", "cost_price_snapshot"):
        with op.batch_alter_table("pos_sale_lines") as batch_op:
            batch_op.drop_column("cost_price_snapshot")
