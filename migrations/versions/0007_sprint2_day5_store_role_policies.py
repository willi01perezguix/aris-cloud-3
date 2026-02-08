"""sprint2 day5 store role policies

Revision ID: 0007_sprint2_day5
Revises: 0006_sprint2_day3
Create Date: 2024-02-05 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_sprint2_day5"
down_revision = "0006_sprint2_day3"
branch_labels = None
depends_on = None


class GUID(sa.TypeDecorator):
    impl = sa.CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID

            return dialect.type_descriptor(UUID(as_uuid=True))
        return dialect.type_descriptor(sa.CHAR(36))


def upgrade() -> None:
    op.create_table(
        "store_role_policies",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("tenant_id", GUID(), nullable=False),
        sa.Column("store_id", GUID(), nullable=False),
        sa.Column("role_name", sa.String(length=100), nullable=False),
        sa.Column("permission_code", sa.String(length=150), nullable=False),
        sa.Column("effect", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.UniqueConstraint(
            "tenant_id",
            "store_id",
            "role_name",
            "permission_code",
            name="uq_store_role_policy_permission",
        ),
    )
    op.create_index("ix_store_role_policies_tenant_id", "store_role_policies", ["tenant_id"])
    op.create_index("ix_store_role_policies_store_id", "store_role_policies", ["store_id"])
    op.create_index(
        "ix_store_role_policies_permission_code",
        "store_role_policies",
        ["permission_code"],
    )


def downgrade() -> None:
    op.drop_index("ix_store_role_policies_permission_code", table_name="store_role_policies")
    op.drop_index("ix_store_role_policies_store_id", table_name="store_role_policies")
    op.drop_index("ix_store_role_policies_tenant_id", table_name="store_role_policies")
    op.drop_table("store_role_policies")
