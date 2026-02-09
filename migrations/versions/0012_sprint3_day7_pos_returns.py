"""sprint3 day7 pos returns

Revision ID: 0012_sprint3_day7_pos_returns
Revises: 0011_sprint3_day6
Create Date: 2025-02-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0012_sprint3_day7_pos_returns"
down_revision = "0011_sprint3_day6"
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
        "return_policy_settings",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("tenant_id", GUID(), nullable=False),
        sa.Column("return_window_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("require_receipt", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("allow_refund_cash", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("allow_refund_card", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("allow_refund_transfer", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("allow_exchange", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("require_manager_for_exceptions", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("accepted_conditions", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("non_reusable_label_strategy", sa.String(length=50), nullable=False, server_default="ASSIGN_NEW_EPC"),
        sa.Column("restocking_fee_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.UniqueConstraint("tenant_id", name="uq_return_policy_settings_tenant_id"),
    )
    op.create_index("ix_return_policy_settings_tenant_id", "return_policy_settings", ["tenant_id"])

    op.create_table(
        "pos_return_events",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("tenant_id", GUID(), nullable=False),
        sa.Column("store_id", GUID(), nullable=False),
        sa.Column("sale_id", GUID(), nullable=False),
        sa.Column("exchange_sale_id", GUID(), nullable=True),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("refund_subtotal", sa.Float(), nullable=False, server_default="0"),
        sa.Column("restocking_fee", sa.Float(), nullable=False, server_default="0"),
        sa.Column("refund_total", sa.Float(), nullable=False, server_default="0"),
        sa.Column("exchange_total", sa.Float(), nullable=False, server_default="0"),
        sa.Column("net_adjustment", sa.Float(), nullable=False, server_default="0"),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["sale_id"], ["pos_sales.id"]),
    )
    op.create_index("ix_pos_return_events_sale_id", "pos_return_events", ["sale_id"])
    op.create_index("ix_pos_return_events_store_id", "pos_return_events", ["store_id"])
    op.create_index("ix_pos_return_events_tenant_id", "pos_return_events", ["tenant_id"])
    op.create_index("ix_pos_return_events_exchange_sale_id", "pos_return_events", ["exchange_sale_id"])


def downgrade() -> None:
    op.drop_index("ix_pos_return_events_exchange_sale_id", table_name="pos_return_events")
    op.drop_index("ix_pos_return_events_tenant_id", table_name="pos_return_events")
    op.drop_index("ix_pos_return_events_store_id", table_name="pos_return_events")
    op.drop_index("ix_pos_return_events_sale_id", table_name="pos_return_events")
    op.drop_table("pos_return_events")

    op.drop_index("ix_return_policy_settings_tenant_id", table_name="return_policy_settings")
    op.drop_table("return_policy_settings")
