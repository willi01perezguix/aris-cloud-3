"""add transfer line price snapshot fields

Revision ID: 0019_sprint8_dayx_transfer_line_prices
Revises: 0018_s8dx_stock_base_prices
Create Date: 2026-02-24
"""

from alembic import op
import sqlalchemy as sa


revision = "0019_sprint8_dayx_transfer_line_prices"
down_revision = "0018_s8dx_stock_base_prices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("transfer_lines", sa.Column("cost_price", sa.Numeric(12, 2), nullable=True))
    op.add_column("transfer_lines", sa.Column("suggested_price", sa.Numeric(12, 2), nullable=True))
    op.add_column("transfer_lines", sa.Column("sale_price", sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("transfer_lines", "sale_price")
    op.drop_column("transfer_lines", "suggested_price")
    op.drop_column("transfer_lines", "cost_price")
