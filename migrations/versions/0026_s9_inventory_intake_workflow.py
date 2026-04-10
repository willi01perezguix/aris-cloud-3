"""s9 inventory intake workflow

Revision ID: 0026_s9_inventory_intake_workflow
Revises: 0025_s8dx_resource_purge_locks
Create Date: 2026-04-09 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


class GUID(sa.TypeDecorator):
    impl = sa.CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID

            return dialect.type_descriptor(UUID(as_uuid=True))
        return dialect.type_descriptor(sa.CHAR(36))


revision = "0026_s9_inventory_intake_workflow"
down_revision = "0025_s8dx_resource_purge_locks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("stock_items") as batch_op:
        batch_op.add_column(sa.Column("item_uid", sa.String(length=36), nullable=False, server_default="00000000-0000-0000-0000-000000000000"))
        batch_op.add_column(sa.Column("item_status", sa.String(length=50), nullable=False, server_default="PENDING"))
        batch_op.add_column(sa.Column("epc_status", sa.String(length=50), nullable=False, server_default="AVAILABLE"))
        batch_op.add_column(sa.Column("observation", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("print_status", sa.String(length=50), nullable=False, server_default="NOT_REQUESTED"))
        batch_op.add_column(sa.Column("issue_state", sa.String(length=50), nullable=True))

    op.execute("UPDATE stock_items SET item_uid = id WHERE item_uid = '00000000-0000-0000-0000-000000000000'")
    with op.batch_alter_table("stock_items") as batch_op:
        batch_op.alter_column("item_uid", server_default=None)
    op.create_index("ix_stock_items_item_uid", "stock_items", ["item_uid"], unique=False)
    op.create_index("uq_stock_items_tenant_item_uid", "stock_items", ["tenant_id", "item_uid"], unique=True)

    op.create_table(
        "epc_assignments",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("tenant_id", GUID(), nullable=False),
        sa.Column("store_id", GUID(), nullable=True),
        sa.Column("epc", sa.String(length=255), nullable=False),
        sa.Column("item_uid", GUID(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(), nullable=False),
        sa.Column("released_at", sa.DateTime(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_release_reason", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="ASSIGNED"),
        sa.Column("sale_line_id", GUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["sale_line_id"], ["pos_sale_lines.id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_epc_assignments_tenant_epc_active", "epc_assignments", ["tenant_id", "epc", "active"], unique=False)
    op.create_index("ix_epc_assignments_epc", "epc_assignments", ["epc"], unique=False)
    op.create_index(
        "uq_epc_assignments_active_epc",
        "epc_assignments",
        ["tenant_id", "epc"],
        unique=True,
        sqlite_where=sa.text("active = 1"),
        postgresql_where=sa.text("active = true"),
    )

    op.create_table(
        "sku_images",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("tenant_id", GUID(), nullable=False),
        sa.Column("sku", sa.String(length=100), nullable=False),
        sa.Column("asset_id", GUID(), nullable=False),
        sa.Column("file_hash", sa.String(length=128), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "sku", "asset_id", name="uq_sku_images_tenant_sku_asset"),
    )

    op.create_table(
        "preload_sessions",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("tenant_id", GUID(), nullable=False),
        sa.Column("store_id", GUID(), nullable=True),
        sa.Column("source_file_name", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="ACTIVE"),
        sa.Column("created_by_user_id", GUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "preload_lines",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("preload_session_id", GUID(), nullable=False),
        sa.Column("item_uid", GUID(), nullable=False),
        sa.Column("tenant_id", GUID(), nullable=False),
        sa.Column("store_id", GUID(), nullable=True),
        sa.Column("sku", sa.String(length=100), nullable=True),
        sa.Column("epc", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("var1_value", sa.String(length=100), nullable=True),
        sa.Column("var2_value", sa.String(length=100), nullable=True),
        sa.Column("pool", sa.String(length=100), nullable=True),
        sa.Column("location_code", sa.String(length=100), nullable=True),
        sa.Column("vendible", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("cost_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("suggested_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("sale_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("item_status", sa.String(length=50), nullable=False, server_default="PENDING"),
        sa.Column("epc_status", sa.String(length=50), nullable=False, server_default="AVAILABLE"),
        sa.Column("observation", sa.Text(), nullable=True),
        sa.Column("image_mode", sa.String(length=20), nullable=False, server_default="blank"),
        sa.Column("image_asset_id", GUID(), nullable=True),
        sa.Column("print_status", sa.String(length=50), nullable=False, server_default="NOT_REQUESTED"),
        sa.Column("source_file_name", sa.String(length=255), nullable=True),
        sa.Column("source_row_number", sa.Integer(), nullable=True),
        sa.Column("lifecycle_state", sa.String(length=50), nullable=False, server_default="STAGING"),
        sa.Column("saved_stock_item_id", GUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["preload_session_id"], ["preload_sessions.id"]),
        sa.ForeignKeyConstraint(["saved_stock_item_id"], ["stock_items.id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    with op.batch_alter_table("pos_sales") as batch_op:
        batch_op.add_column(sa.Column("sale_code", sa.String(length=100), nullable=True))
    op.create_index("ix_pos_sales_sale_code", "pos_sales", ["sale_code"], unique=False)

    with op.batch_alter_table("pos_sale_lines") as batch_op:
        batch_op.add_column(sa.Column("sale_line_id", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("item_uid", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("sku_snapshot", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("description_snapshot", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("var1_snapshot", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("var2_snapshot", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("sale_price_snapshot", sa.Numeric(precision=12, scale=2), nullable=True))
        batch_op.add_column(sa.Column("epc_at_sale", sa.String(length=255), nullable=True))
    op.create_index("ix_pos_sale_lines_sale_line_id", "pos_sale_lines", ["sale_line_id"], unique=False)
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
    with op.batch_alter_table("pos_sales") as batch_op:
        batch_op.drop_column("sale_code")

    op.drop_table("preload_lines")
    op.drop_table("preload_sessions")
    op.drop_table("sku_images")
    op.drop_index("uq_epc_assignments_active_epc", table_name="epc_assignments")
    op.drop_index("ix_epc_assignments_epc", table_name="epc_assignments")
    op.drop_index("ix_epc_assignments_tenant_epc_active", table_name="epc_assignments")
    op.drop_table("epc_assignments")

    op.drop_index("uq_stock_items_tenant_item_uid", table_name="stock_items")
    op.drop_index("ix_stock_items_item_uid", table_name="stock_items")
    with op.batch_alter_table("stock_items") as batch_op:
        batch_op.drop_column("issue_state")
        batch_op.drop_column("print_status")
        batch_op.drop_column("observation")
        batch_op.drop_column("epc_status")
        batch_op.drop_column("item_status")
        batch_op.drop_column("item_uid")
