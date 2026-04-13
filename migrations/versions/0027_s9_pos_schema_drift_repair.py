"""s9 pos schema drift repair

Revision ID: 0027_s9_pos_schema_drift_repair
Revises: 0026_s9_inventory_intake_workflow
Create Date: 2026-04-13 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0027_s9_pos_schema_drift_repair"
down_revision = "0026_s9_inventory_intake_workflow"
branch_labels = None
depends_on = None


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_column(inspector, "pos_sales", "receipt_number"):
        with op.batch_alter_table("pos_sales") as batch_op:
            batch_op.add_column(sa.Column("receipt_number", sa.String(length=100), nullable=True))
    if not _has_column(inspector, "pos_sales", "sale_code"):
        with op.batch_alter_table("pos_sales") as batch_op:
            batch_op.add_column(sa.Column("sale_code", sa.String(length=100), nullable=True))

    if not _has_index(inspector, "pos_sales", "ix_pos_sales_tenant_store_receipt"):
        op.create_index(
            "ix_pos_sales_tenant_store_receipt",
            "pos_sales",
            ["tenant_id", "store_id", "receipt_number"],
            unique=False,
        )
    if not _has_index(inspector, "pos_sales", "ix_pos_sales_sale_code"):
        op.create_index("ix_pos_sales_sale_code", "pos_sales", ["sale_code"], unique=False)

    with op.batch_alter_table("pos_sale_lines") as batch_op:
        if not _has_column(inspector, "pos_sale_lines", "sale_line_id"):
            batch_op.add_column(sa.Column("sale_line_id", sa.String(length=100), nullable=True))
        if not _has_column(inspector, "pos_sale_lines", "item_uid"):
            batch_op.add_column(sa.Column("item_uid", sa.String(length=36), nullable=True))
        if not _has_column(inspector, "pos_sale_lines", "sku_snapshot"):
            batch_op.add_column(sa.Column("sku_snapshot", sa.String(length=100), nullable=True))
        if not _has_column(inspector, "pos_sale_lines", "description_snapshot"):
            batch_op.add_column(sa.Column("description_snapshot", sa.Text(), nullable=True))
        if not _has_column(inspector, "pos_sale_lines", "var1_snapshot"):
            batch_op.add_column(sa.Column("var1_snapshot", sa.String(length=100), nullable=True))
        if not _has_column(inspector, "pos_sale_lines", "var2_snapshot"):
            batch_op.add_column(sa.Column("var2_snapshot", sa.String(length=100), nullable=True))
        if not _has_column(inspector, "pos_sale_lines", "sale_price_snapshot"):
            batch_op.add_column(sa.Column("sale_price_snapshot", sa.Numeric(precision=12, scale=2), nullable=True))
        if not _has_column(inspector, "pos_sale_lines", "epc_at_sale"):
            batch_op.add_column(sa.Column("epc_at_sale", sa.String(length=255), nullable=True))

    if not _has_index(inspector, "pos_sale_lines", "ix_pos_sale_lines_sale_line_id"):
        op.create_index("ix_pos_sale_lines_sale_line_id", "pos_sale_lines", ["sale_line_id"], unique=False)
    if not _has_index(inspector, "pos_sale_lines", "ix_pos_sale_lines_item_uid"):
        op.create_index("ix_pos_sale_lines_item_uid", "pos_sale_lines", ["item_uid"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pos_sale_lines_item_uid", table_name="pos_sale_lines")
    op.drop_index("ix_pos_sale_lines_sale_line_id", table_name="pos_sale_lines")
    with op.batch_alter_table("pos_sale_lines") as batch_op:
        batch_op.drop_column("epc_at_sale")
        batch_op.drop_column("sale_price_snapshot")
        batch_op.drop_column("var2_snapshot")
        batch_op.drop_column("var1_snapshot")
        batch_op.drop_column("description_snapshot")
        batch_op.drop_column("sku_snapshot")
        batch_op.drop_column("item_uid")
        batch_op.drop_column("sale_line_id")

    op.drop_index("ix_pos_sales_sale_code", table_name="pos_sales")
    op.drop_index("ix_pos_sales_tenant_store_receipt", table_name="pos_sales")
    with op.batch_alter_table("pos_sales") as batch_op:
        batch_op.drop_column("sale_code")
        batch_op.drop_column("receipt_number")
