"""add store_id to stock_items for store traceability

Revision ID: 0020_s8dx_stock_store_scope
Revises: 0019_sprint8_dayx_transfer_line_prices
Create Date: 2026-02-24
"""

from alembic import op
import sqlalchemy as sa


revision = "0020_s8dx_stock_store_scope"
down_revision = "0019_sprint8_dayx_transfer_line_prices"
branch_labels = None
depends_on = None


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _fk_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {fk["name"] for fk in inspector.get_foreign_keys(table_name) if fk.get("name")}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {idx["name"] for idx in inspector.get_indexes(table_name) if idx.get("name")}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = _column_names(inspector, "stock_items")
    fks = _fk_names(inspector, "stock_items")
    indexes = _index_names(inspector, "stock_items")

    with op.batch_alter_table("stock_items") as batch_op:
        if "store_id" not in columns:
            batch_op.add_column(sa.Column("store_id", sa.UUID(), nullable=True))
        if "fk_stock_items_store_id_stores" not in fks:
            batch_op.create_foreign_key("fk_stock_items_store_id_stores", "stores", ["store_id"], ["id"])
        if "ix_stock_items_store_id" not in indexes:
            batch_op.create_index("ix_stock_items_store_id", ["store_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = _column_names(inspector, "stock_items")
    fks = _fk_names(inspector, "stock_items")
    indexes = _index_names(inspector, "stock_items")

    with op.batch_alter_table("stock_items") as batch_op:
        if "ix_stock_items_store_id" in indexes:
            batch_op.drop_index("ix_stock_items_store_id")
        if "fk_stock_items_store_id_stores" in fks:
            batch_op.drop_constraint("fk_stock_items_store_id_stores", type_="foreignkey")
        if "store_id" in columns:
            batch_op.drop_column("store_id")
