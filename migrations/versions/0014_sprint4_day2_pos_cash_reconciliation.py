"""sprint4 day2 pos cash reconciliation

Revision ID: 0014_sprint4_day2
Revises: 0013_sprint4_day1
Create Date: 2024-02-21 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0014_sprint4_day2"
down_revision = "0013_sprint4_day1"
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
    with op.batch_alter_table("pos_cash_movements") as batch_op:
        batch_op.alter_column("cash_session_id", existing_type=GUID(), nullable=True)
        batch_op.add_column(sa.Column("actor_user_id", GUID(), nullable=True))
        batch_op.add_column(sa.Column("trace_id", sa.String(length=255), nullable=True))
        batch_op.add_column(
            sa.Column("occurred_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"))
        )
        batch_op.create_index("ix_pos_cash_movements_actor_user_id", ["actor_user_id"])
        batch_op.create_index("ix_pos_cash_movements_occurred_at", ["occurred_at"])

    op.add_column("pos_cash_day_closes", sa.Column("expected_cash", sa.Float(), nullable=False, server_default="0"))
    op.add_column("pos_cash_day_closes", sa.Column("counted_cash", sa.Float(), nullable=True))
    op.add_column("pos_cash_day_closes", sa.Column("difference_amount", sa.Float(), nullable=True))
    op.add_column("pos_cash_day_closes", sa.Column("difference_type", sa.String(length=10), nullable=True))
    op.add_column("pos_cash_day_closes", sa.Column("net_cash_sales", sa.Float(), nullable=False, server_default="0"))
    op.add_column("pos_cash_day_closes", sa.Column("cash_refunds", sa.Float(), nullable=False, server_default="0"))
    op.add_column("pos_cash_day_closes", sa.Column("net_cash_movement", sa.Float(), nullable=False, server_default="0"))
    op.add_column("pos_cash_day_closes", sa.Column("day_close_difference", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("pos_cash_day_closes", "day_close_difference")
    op.drop_column("pos_cash_day_closes", "net_cash_movement")
    op.drop_column("pos_cash_day_closes", "cash_refunds")
    op.drop_column("pos_cash_day_closes", "net_cash_sales")
    op.drop_column("pos_cash_day_closes", "difference_type")
    op.drop_column("pos_cash_day_closes", "difference_amount")
    op.drop_column("pos_cash_day_closes", "counted_cash")
    op.drop_column("pos_cash_day_closes", "expected_cash")

    with op.batch_alter_table("pos_cash_movements") as batch_op:
        batch_op.drop_index("ix_pos_cash_movements_occurred_at")
        batch_op.drop_index("ix_pos_cash_movements_actor_user_id")
        batch_op.drop_column("occurred_at")
        batch_op.drop_column("trace_id")
        batch_op.drop_column("actor_user_id")
        batch_op.alter_column("cash_session_id", existing_type=GUID(), nullable=False)
