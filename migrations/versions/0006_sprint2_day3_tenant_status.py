"""sprint2 day3 tenant status

Revision ID: 0006_sprint2_day3
Revises: 0005_sprint2_day2
Create Date: 2024-01-04 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_sprint2_day3"
down_revision = "0005_sprint2_day2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("status", sa.String(length=50), nullable=False, server_default="active"),
    )
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("tenants", "status", server_default=None)


def downgrade() -> None:
    op.drop_column("tenants", "status")
