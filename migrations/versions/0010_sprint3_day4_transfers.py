"""sprint3 day4 transfers

Revision ID: 0010_sprint3_day4
Revises: 0009_sprint3_day2
Create Date: 2024-02-08 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_sprint3_day4"
down_revision = "0009_sprint3_day2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    class GUID(sa.TypeDecorator):
        impl = sa.CHAR
        cache_ok = True

        def load_dialect_impl(self, dialect):
            if dialect.name == "postgresql":
                from sqlalchemy.dialects.postgresql import UUID

                return dialect.type_descriptor(UUID(as_uuid=True))
            return dialect.type_descriptor(sa.CHAR(36))

    op.create_table(
        "transfers",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), nullable=False, index=True),
        sa.Column("origin_store_id", GUID(), nullable=False, index=True),
        sa.Column("destination_store_id", GUID(), nullable=False, index=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="DRAFT"),
        sa.Column("created_by_user_id", GUID(), nullable=True),
        sa.Column("updated_by_user_id", GUID(), nullable=True),
        sa.Column("dispatched_by_user_id", GUID(), nullable=True),
        sa.Column("canceled_by_user_id", GUID(), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(), nullable=True),
        sa.Column("canceled_at", sa.DateTime(), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "transfer_lines",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("transfer_id", GUID(), nullable=False, index=True),
        sa.Column("tenant_id", GUID(), nullable=False, index=True),
        sa.Column("line_type", sa.String(length=20), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sku", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("var1_value", sa.String(length=100), nullable=True),
        sa.Column("var2_value", sa.String(length=100), nullable=True),
        sa.Column("epc", sa.String(length=255), nullable=True),
        sa.Column("location_code", sa.String(length=100), nullable=True),
        sa.Column("pool", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("location_is_vendible", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("image_asset_id", GUID(), nullable=True),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("image_thumb_url", sa.String(length=500), nullable=True),
        sa.Column("image_source", sa.String(length=100), nullable=True),
        sa.Column("image_updated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "transfer_movements",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), nullable=False, index=True),
        sa.Column("transfer_id", GUID(), nullable=False, index=True),
        sa.Column("transfer_line_id", GUID(), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("from_location_code", sa.String(length=100), nullable=True),
        sa.Column("from_pool", sa.String(length=100), nullable=True),
        sa.Column("to_location_code", sa.String(length=100), nullable=True),
        sa.Column("to_pool", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("qty", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("transfer_movements")
    op.drop_table("transfer_lines")
    op.drop_table("transfers")
