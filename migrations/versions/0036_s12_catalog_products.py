"""s12 catalog products and cost history

Revision ID: 0036_s12_catalog_products
Revises: 0035_s12_ai_preload_extractions
Create Date: 2026-04-19
"""

from alembic import op
import sqlalchemy as sa
import uuid


revision = "0036_s12_catalog_products"
down_revision = "0035_s12_ai_preload_extractions"
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

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(uuid.UUID(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


def upgrade() -> None:
    op.create_table(
        "catalog_products",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("tenant_id", GUID(), nullable=False),
        sa.Column("sku", sa.String(length=100), nullable=False),
        sa.Column("normalized_sku", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("brand", sa.String(length=120), nullable=True),
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column("style", sa.String(length=120), nullable=True),
        sa.Column("variant_1", sa.String(length=120), nullable=True),
        sa.Column("variant_2", sa.String(length=120), nullable=True),
        sa.Column("normalized_variant_1", sa.String(length=120), nullable=True),
        sa.Column("normalized_variant_2", sa.String(length=120), nullable=True),
        sa.Column("color", sa.String(length=100), nullable=True),
        sa.Column("size", sa.String(length=100), nullable=True),
        sa.Column("default_pool", sa.String(length=100), nullable=True),
        sa.Column("default_location_code", sa.String(length=100), nullable=True),
        sa.Column("sellable_default", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_cost_gtq", sa.Numeric(12, 2), nullable=True),
        sa.Column("last_original_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("last_source_currency", sa.String(length=12), nullable=True),
        sa.Column("last_exchange_rate_to_gtq", sa.Numeric(12, 4), nullable=True),
        sa.Column("suggested_price_gtq", sa.Numeric(12, 2), nullable=True),
        sa.Column("default_sale_price_gtq", sa.Numeric(12, 2), nullable=True),
        sa.Column("reference_price_original", sa.Numeric(12, 2), nullable=True),
        sa.Column("reference_price_gtq", sa.Numeric(12, 2), nullable=True),
        sa.Column("last_source_supplier", sa.String(length=255), nullable=True),
        sa.Column("last_source_order_number", sa.String(length=255), nullable=True),
        sa.Column("last_source_order_date", sa.Date(), nullable=True),
        sa.Column("price_review_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'ACTIVE'")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "normalized_sku", "normalized_variant_1", "normalized_variant_2", name="uq_catalog_product_identity"),
    )
    op.create_index("ix_catalog_products_tenant_id", "catalog_products", ["tenant_id"])

    op.create_table(
        "catalog_product_cost_history",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("tenant_id", GUID(), nullable=False),
        sa.Column("catalog_product_id", GUID(), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("source_extraction_id", GUID(), nullable=True),
        sa.Column("source_preload_session_id", GUID(), nullable=True),
        sa.Column("source_preload_line_id", GUID(), nullable=True),
        sa.Column("source_order_number", sa.String(length=255), nullable=True),
        sa.Column("source_order_date", sa.Date(), nullable=True),
        sa.Column("source_supplier", sa.String(length=255), nullable=True),
        sa.Column("original_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("source_currency", sa.String(length=12), nullable=True),
        sa.Column("exchange_rate_to_gtq", sa.Numeric(12, 4), nullable=True),
        sa.Column("cost_gtq", sa.Numeric(12, 2), nullable=False),
        sa.Column("suggested_price_gtq", sa.Numeric(12, 2), nullable=True),
        sa.Column("reference_price_original", sa.Numeric(12, 2), nullable=True),
        sa.Column("reference_price_gtq", sa.Numeric(12, 2), nullable=True),
        sa.Column("created_by_user_id", GUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["catalog_product_id"], ["catalog_products.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["source_extraction_id"], ["stock_ai_extractions.id"]),
        sa.ForeignKeyConstraint(["source_preload_line_id"], ["preload_lines.id"]),
        sa.ForeignKeyConstraint(["source_preload_session_id"], ["preload_sessions.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_catalog_product_cost_history_tenant_id", "catalog_product_cost_history", ["tenant_id"])
    op.create_index("ix_catalog_product_cost_history_catalog_product_id", "catalog_product_cost_history", ["catalog_product_id"])
    op.create_index("ix_catalog_product_cost_history_source_extraction_id", "catalog_product_cost_history", ["source_extraction_id"])
    op.create_index("ix_catalog_product_cost_history_source_preload_session_id", "catalog_product_cost_history", ["source_preload_session_id"])
    op.create_index("ix_catalog_product_cost_history_source_preload_line_id", "catalog_product_cost_history", ["source_preload_line_id"])

    with op.batch_alter_table("preload_lines") as batch_op:
        batch_op.add_column(sa.Column("catalog_product_id", GUID(), nullable=True))
        batch_op.create_foreign_key("fk_preload_lines_catalog_product_id", "catalog_products", ["catalog_product_id"], ["id"])
        batch_op.create_index("ix_preload_lines_catalog_product_id", ["catalog_product_id"], unique=False)

    with op.batch_alter_table("stock_items") as batch_op:
        batch_op.add_column(sa.Column("catalog_product_id", GUID(), nullable=True))
        batch_op.create_foreign_key("fk_stock_items_catalog_product_id", "catalog_products", ["catalog_product_id"], ["id"])
        batch_op.create_index("ix_stock_items_catalog_product_id", ["catalog_product_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("stock_items") as batch_op:
        batch_op.drop_index("ix_stock_items_catalog_product_id")
        batch_op.drop_constraint("fk_stock_items_catalog_product_id", type_="foreignkey")
        batch_op.drop_column("catalog_product_id")

    with op.batch_alter_table("preload_lines") as batch_op:
        batch_op.drop_index("ix_preload_lines_catalog_product_id")
        batch_op.drop_constraint("fk_preload_lines_catalog_product_id", type_="foreignkey")
        batch_op.drop_column("catalog_product_id")

    op.drop_index("ix_catalog_product_cost_history_source_preload_line_id", table_name="catalog_product_cost_history")
    op.drop_index("ix_catalog_product_cost_history_source_preload_session_id", table_name="catalog_product_cost_history")
    op.drop_index("ix_catalog_product_cost_history_source_extraction_id", table_name="catalog_product_cost_history")
    op.drop_index("ix_catalog_product_cost_history_catalog_product_id", table_name="catalog_product_cost_history")
    op.drop_index("ix_catalog_product_cost_history_tenant_id", table_name="catalog_product_cost_history")
    op.drop_table("catalog_product_cost_history")

    op.drop_index("ix_catalog_products_tenant_id", table_name="catalog_products")
    op.drop_table("catalog_products")
