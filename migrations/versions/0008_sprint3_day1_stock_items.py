"""sprint3 day1 stock items

Revision ID: 0008_sprint3_day1
Revises: 0007_sprint2_day5
Create Date: 2024-02-06 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_sprint3_day1"
down_revision = "0007_sprint2_day5"
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
        "stock_items",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("tenant_id", GUID(), nullable=False),
        sa.Column("sku", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("var1_value", sa.String(length=100), nullable=True),
        sa.Column("var2_value", sa.String(length=100), nullable=True),
        sa.Column("epc", sa.String(length=255), nullable=True),
        sa.Column("location_code", sa.String(length=100), nullable=True),
        sa.Column("pool", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("location_is_vendible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("image_asset_id", GUID(), nullable=True),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("image_thumb_url", sa.String(length=500), nullable=True),
        sa.Column("image_source", sa.String(length=100), nullable=True),
        sa.Column("image_updated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
    )
    op.create_index("ix_stock_items_tenant_id", "stock_items", ["tenant_id"])
    op.create_index("ix_stock_items_sku", "stock_items", ["sku"])
    op.create_index("ix_stock_items_epc", "stock_items", ["epc"])
    op.create_index("ix_stock_items_location_code", "stock_items", ["location_code"])
    op.create_index("ix_stock_items_pool", "stock_items", ["pool"])
    op.create_index("ix_stock_items_status", "stock_items", ["status"])
    op.create_index("ix_stock_items_created_at", "stock_items", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_stock_items_created_at", table_name="stock_items")
    op.drop_index("ix_stock_items_status", table_name="stock_items")
    op.drop_index("ix_stock_items_pool", table_name="stock_items")
    op.drop_index("ix_stock_items_location_code", table_name="stock_items")
    op.drop_index("ix_stock_items_epc", table_name="stock_items")
    op.drop_index("ix_stock_items_sku", table_name="stock_items")
    op.drop_index("ix_stock_items_tenant_id", table_name="stock_items")
    op.drop_table("stock_items")
