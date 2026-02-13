"""sprint3 day6 pos sales

Revision ID: 0011_sprint3_day6
Revises: 0010_sprint3_day4
Create Date: 2024-02-12 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_sprint3_day6"
down_revision = "0010_sprint3_day4"
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
        "pos_sales",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), nullable=False, index=True),
        sa.Column("store_id", GUID(), nullable=False, index=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="DRAFT"),
        sa.Column("total_due", sa.Float(), nullable=False, server_default="0"),
        sa.Column("paid_total", sa.Float(), nullable=False, server_default="0"),
        sa.Column("balance_due", sa.Float(), nullable=False, server_default="0"),
        sa.Column("change_due", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_by_user_id", GUID(), nullable=True),
        sa.Column("updated_by_user_id", GUID(), nullable=True),
        sa.Column("checked_out_by_user_id", GUID(), nullable=True),
        sa.Column("canceled_by_user_id", GUID(), nullable=True),
        sa.Column("checked_out_at", sa.DateTime(), nullable=True),
        sa.Column("canceled_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "pos_sale_lines",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("sale_id", GUID(), nullable=False, index=True),
        sa.Column("tenant_id", GUID(), nullable=False, index=True),
        sa.Column("line_type", sa.String(length=20), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("line_total", sa.Float(), nullable=False, server_default="0"),
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
        "pos_payments",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("sale_id", GUID(), nullable=False, index=True),
        sa.Column("tenant_id", GUID(), nullable=False, index=True),
        sa.Column("method", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("authorization_code", sa.String(length=100), nullable=True),
        sa.Column("bank_name", sa.String(length=100), nullable=True),
        sa.Column("voucher_number", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "pos_cash_sessions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), nullable=False, index=True),
        sa.Column("store_id", GUID(), nullable=False, index=True),
        sa.Column("cashier_user_id", GUID(), nullable=False, index=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="OPEN"),
        sa.Column("opened_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "pos_cash_movements",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), nullable=False, index=True),
        sa.Column("store_id", GUID(), nullable=False, index=True),
        sa.Column("cash_session_id", GUID(), nullable=False, index=True),
        sa.Column("sale_id", GUID(), nullable=True, index=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("pos_cash_movements")
    op.drop_table("pos_cash_sessions")
    op.drop_table("pos_payments")
    op.drop_table("pos_sale_lines")
    op.drop_table("pos_sales")
