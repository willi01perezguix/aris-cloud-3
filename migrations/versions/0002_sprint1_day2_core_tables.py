"""sprint1 day2 core tables

Revision ID: 0002_sprint1_day2
Revises: 0001_initial
Create Date: 2024-01-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_sprint1_day2"
down_revision = "0001_initial"
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
        "permission_catalog",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("code", sa.String(length=150), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_permission_catalog_code", "permission_catalog", ["code"], unique=True)
    op.create_table(
        "role_templates",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), sa.ForeignKey("tenants.id"), nullable=True, index=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "name", name="uq_role_templates_tenant_name"),
    )
    op.create_table(
        "role_template_permissions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("role_template_id", GUID(), sa.ForeignKey("role_templates.id"), nullable=False),
        sa.Column("permission_id", GUID(), sa.ForeignKey("permission_catalog.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("role_template_id", "permission_id", name="uq_role_template_permission"),
    )
    with op.batch_alter_table("stores") as batch_op:
        batch_op.create_unique_constraint("uq_store_tenant_name", ["tenant_id", "name"])
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("store_id", GUID(), nullable=True))
        batch_op.add_column(sa.Column("status", sa.String(length=50), nullable=False, server_default="active"))
        batch_op.create_foreign_key("fk_users_store_id", "stores", ["store_id"], ["id"])
        batch_op.drop_index("ix_users_username")
        batch_op.drop_index("ix_users_email")
        batch_op.create_unique_constraint("uq_users_tenant_username", ["tenant_id", "username"])
        batch_op.create_unique_constraint("uq_users_tenant_email", ["tenant_id", "email"])
        batch_op.alter_column("status", server_default=None)
    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.alter_column("user_id", existing_type=GUID(), nullable=True)
        batch_op.add_column(sa.Column("trace_id", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("actor", sa.String(length=255), nullable=False, server_default="system"))
        batch_op.add_column(sa.Column("entity", sa.String(length=255), nullable=False, server_default="unknown"))
        batch_op.add_column(sa.Column("before_payload", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("after_payload", sa.JSON(), nullable=True))
        batch_op.create_index("ix_audit_events_trace_id", ["trace_id"])
        batch_op.alter_column("actor", server_default=None)
        batch_op.alter_column("entity", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.drop_index("ix_audit_events_trace_id")
        batch_op.drop_column("after_payload")
        batch_op.drop_column("before_payload")
        batch_op.drop_column("entity")
        batch_op.drop_column("actor")
        batch_op.drop_column("trace_id")
        batch_op.alter_column("user_id", existing_type=GUID(), nullable=False)
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("uq_users_tenant_email", type_="unique")
        batch_op.drop_constraint("uq_users_tenant_username", type_="unique")
        batch_op.create_index("ix_users_email", ["email"], unique=True)
        batch_op.create_index("ix_users_username", ["username"], unique=True)
        batch_op.drop_constraint("fk_users_store_id", type_="foreignkey")
        batch_op.drop_column("status")
        batch_op.drop_column("store_id")
    with op.batch_alter_table("stores") as batch_op:
        batch_op.drop_constraint("uq_store_tenant_name", type_="unique")
    op.drop_table("role_template_permissions")
    op.drop_table("role_templates")
    op.drop_index("ix_permission_catalog_code", table_name="permission_catalog")
    op.drop_table("permission_catalog")
