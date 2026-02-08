"""sprint2 day2 admin core settings

Revision ID: 0005_sprint2_day2
Revises: 0004_sprint2_day1
Create Date: 2024-01-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_sprint2_day2"
down_revision = "0004_sprint2_day1"
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
        "variant_field_settings",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("var1_label", sa.String(length=255), nullable=True),
        sa.Column("var2_label", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", name="uq_variant_field_settings_tenant_id"),
    )


def downgrade() -> None:
    op.drop_table("variant_field_settings")
