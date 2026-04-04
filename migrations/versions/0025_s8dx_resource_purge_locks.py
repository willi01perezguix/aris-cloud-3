"""s8dx resource purge locks

Revision ID: 0025_s8dx_resource_purge_locks
Revises: 0024_s8dx_tenant_purge_lock
Create Date: 2026-04-04 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0025_s8dx_resource_purge_locks"
down_revision = "0024_s8dx_tenant_purge_lock"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purge_locks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("resource_type", sa.String(length=30), nullable=False),
        sa.Column("resource_id", sa.String(length=64), nullable=False),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("resource_type", "resource_id", name="uq_purge_locks_resource"),
    )


def downgrade() -> None:
    op.drop_table("purge_locks")
