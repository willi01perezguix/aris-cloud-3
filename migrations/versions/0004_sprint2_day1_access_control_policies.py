"""sprint2 day1 access control policies

Revision ID: 0004_sprint2_day1
Revises: 0003_sprint1_day6
Create Date: 2024-02-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_sprint2_day1"
down_revision = "0003_sprint1_day6"
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
        "tenant_role_policies",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("tenant_id", GUID(), nullable=True),
        sa.Column("role_name", sa.String(length=100), nullable=False),
        sa.Column("permission_code", sa.String(length=150), nullable=False),
        sa.Column("effect", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.UniqueConstraint(
            "tenant_id",
            "role_name",
            "permission_code",
            name="uq_tenant_role_policy_permission",
        ),
    )
    op.create_index("ix_tenant_role_policies_tenant_id", "tenant_role_policies", ["tenant_id"])
    op.create_index("ix_tenant_role_policies_permission_code", "tenant_role_policies", ["permission_code"])

    op.create_table(
        "user_permission_overrides",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("tenant_id", GUID(), nullable=False),
        sa.Column("user_id", GUID(), nullable=False),
        sa.Column("permission_code", sa.String(length=150), nullable=False),
        sa.Column("effect", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint(
            "tenant_id",
            "user_id",
            "permission_code",
            name="uq_user_permission_override",
        ),
    )
    op.create_index("ix_user_permission_overrides_tenant_id", "user_permission_overrides", ["tenant_id"])
    op.create_index("ix_user_permission_overrides_user_id", "user_permission_overrides", ["user_id"])
    op.create_index("ix_user_permission_overrides_permission_code", "user_permission_overrides", ["permission_code"])


def downgrade() -> None:
    op.drop_index("ix_user_permission_overrides_permission_code", table_name="user_permission_overrides")
    op.drop_index("ix_user_permission_overrides_user_id", table_name="user_permission_overrides")
    op.drop_index("ix_user_permission_overrides_tenant_id", table_name="user_permission_overrides")
    op.drop_table("user_permission_overrides")

    op.drop_index("ix_tenant_role_policies_permission_code", table_name="tenant_role_policies")
    op.drop_index("ix_tenant_role_policies_tenant_id", table_name="tenant_role_policies")
    op.drop_table("tenant_role_policies")
