"""sprint4 day1 pos cash core

Revision ID: 0013_sprint4_day1
Revises: 0012_sprint3_day7_pos_returns
Create Date: 2024-02-20 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0013_sprint4_day1"
down_revision = "0012_sprint3_day7_pos_returns"
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
    op.add_column(
        "pos_cash_sessions",
        sa.Column("business_date", sa.Date(), nullable=False, server_default="1970-01-01"),
    )
    op.add_column(
        "pos_cash_sessions",
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
    )
    op.add_column(
        "pos_cash_sessions",
        sa.Column("opening_amount", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "pos_cash_sessions",
        sa.Column("expected_cash", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "pos_cash_sessions",
        sa.Column("counted_cash", sa.Float(), nullable=True),
    )
    op.add_column(
        "pos_cash_sessions",
        sa.Column("difference", sa.Float(), nullable=True),
    )

    op.add_column(
        "pos_cash_movements",
        sa.Column(
            "cashier_user_id",
            GUID(),
            nullable=False,
            server_default="00000000-0000-0000-0000-000000000000",
        ),
    )
    op.add_column(
        "pos_cash_movements",
        sa.Column("business_date", sa.Date(), nullable=False, server_default="1970-01-01"),
    )
    op.add_column(
        "pos_cash_movements",
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
    )
    op.add_column(
        "pos_cash_movements",
        sa.Column("expected_balance_before", sa.Float(), nullable=True),
    )
    op.add_column(
        "pos_cash_movements",
        sa.Column("expected_balance_after", sa.Float(), nullable=True),
    )
    op.add_column(
        "pos_cash_movements",
        sa.Column("transaction_id", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "pos_cash_movements",
        sa.Column("reason", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_pos_cash_movements_cashier_user_id", "pos_cash_movements", ["cashier_user_id"])
    op.create_index("ix_pos_cash_movements_business_date", "pos_cash_movements", ["business_date"])

    op.create_table(
        "pos_cash_day_closes",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("tenant_id", GUID(), nullable=False),
        sa.Column("store_id", GUID(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("force_close", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("closed_by_user_id", GUID(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "store_id",
            "business_date",
            name="uq_pos_cash_day_close_store_date",
        ),
    )
    op.create_index("ix_pos_cash_day_closes_tenant_id", "pos_cash_day_closes", ["tenant_id"])
    op.create_index("ix_pos_cash_day_closes_store_id", "pos_cash_day_closes", ["store_id"])
    op.create_index("ix_pos_cash_day_closes_business_date", "pos_cash_day_closes", ["business_date"])


def downgrade() -> None:
    op.drop_index("ix_pos_cash_day_closes_business_date", table_name="pos_cash_day_closes")
    op.drop_index("ix_pos_cash_day_closes_store_id", table_name="pos_cash_day_closes")
    op.drop_index("ix_pos_cash_day_closes_tenant_id", table_name="pos_cash_day_closes")
    op.drop_table("pos_cash_day_closes")

    op.drop_index("ix_pos_cash_movements_business_date", table_name="pos_cash_movements")
    op.drop_index("ix_pos_cash_movements_cashier_user_id", table_name="pos_cash_movements")
    op.drop_column("pos_cash_movements", "reason")
    op.drop_column("pos_cash_movements", "transaction_id")
    op.drop_column("pos_cash_movements", "expected_balance_after")
    op.drop_column("pos_cash_movements", "expected_balance_before")
    op.drop_column("pos_cash_movements", "timezone")
    op.drop_column("pos_cash_movements", "business_date")
    op.drop_column("pos_cash_movements", "cashier_user_id")

    op.drop_column("pos_cash_sessions", "difference")
    op.drop_column("pos_cash_sessions", "counted_cash")
    op.drop_column("pos_cash_sessions", "expected_cash")
    op.drop_column("pos_cash_sessions", "opening_amount")
    op.drop_column("pos_cash_sessions", "timezone")
    op.drop_column("pos_cash_sessions", "business_date")
