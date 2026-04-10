"""s8dx tenant purge lock

Revision ID: 0024_s8dx_tenant_purge_lock
Revises: 0023_s8dx_stock_items_contract_guard
Create Date: 2026-04-04
"""

from alembic import op
import sqlalchemy as sa


class GUID(sa.TypeDecorator):
    impl = sa.CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID

            return dialect.type_descriptor(UUID(as_uuid=True))
        return dialect.type_descriptor(sa.CHAR(36))


# revision identifiers, used by Alembic.
revision = "0024_s8dx_tenant_purge_lock"
down_revision = "0023_s8dx_stock_items_contract_guard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_purge_locks",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("tenant_id", GUID(), nullable=False),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id"),
    )
    op.create_index("ix_tenant_purge_locks_tenant_id", "tenant_purge_locks", ["tenant_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_tenant_purge_locks_tenant_id", table_name="tenant_purge_locks")
    op.drop_table("tenant_purge_locks")
