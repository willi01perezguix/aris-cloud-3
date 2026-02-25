"""ensure stock_items.store_id exists with index and foreign key

Revision ID: 0022_s8dx_stock_items_store_id_hotfix
Revises: 0021_s8dx_stock_import_contract_reconcile
Create Date: 2026-02-25 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0022_s8dx_stock_items_store_id_hotfix"
down_revision = "0021_s8dx_stock_import_contract_reconcile"
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
            batch_op.add_column(sa.Column("store_id", GUID(), nullable=True))
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
