"""s11 advances gift cards cash integration

Revision ID: 0034_s11_advances_gift_cards_cash_integration
Revises: 0033_s11_pos_advances
Create Date: 2026-04-18 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0034_s11_advances_gift_cards_cash_integration"
down_revision = "0033_s11_pos_advances"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pos_advances", sa.Column("voucher_type", sa.String(length=20), nullable=False, server_default="ADVANCE"))
    op.add_column("pos_advances", sa.Column("issued_cash_movement_id", sa.UUID(), nullable=True))
    op.create_index("ix_pos_advances_issued_cash_movement_id", "pos_advances", ["issued_cash_movement_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pos_advances_issued_cash_movement_id", table_name="pos_advances")
    op.drop_column("pos_advances", "issued_cash_movement_id")
    op.drop_column("pos_advances", "voucher_type")
