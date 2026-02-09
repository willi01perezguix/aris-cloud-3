"""sprint4 day4 exports

Revision ID: 0015_sprint4_day4
Revises: 0014_sprint4_day2
Create Date: 2024-02-22 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0015_sprint4_day4"
down_revision = "0014_sprint4_day2"
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
        "export_records",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("tenant_id", GUID(), nullable=False),
        sa.Column("store_id", GUID(), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("format", sa.String(length=10), nullable=False),
        sa.Column("filters_snapshot", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="CREATED"),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("generated_by_user_id", GUID(), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_export_records_tenant_id", "export_records", ["tenant_id"])
    op.create_index("ix_export_records_store_id", "export_records", ["store_id"])
    op.create_index("ix_export_records_tenant_status", "export_records", ["tenant_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_export_records_tenant_status", table_name="export_records")
    op.drop_index("ix_export_records_store_id", table_name="export_records")
    op.drop_index("ix_export_records_tenant_id", table_name="export_records")
    op.drop_table("export_records")
