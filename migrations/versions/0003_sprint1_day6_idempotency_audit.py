"""sprint1 day6 idempotency and audit extensions

Revision ID: 0003_sprint1_day6
Revises: 0002_sprint1_day2
Create Date: 2024-01-06 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_sprint1_day6"
down_revision = "0002_sprint1_day2"
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
    with op.batch_alter_table("idempotency_records") as batch_op:
        batch_op.add_column(sa.Column("method", sa.String(length=16), nullable=False, server_default="POST"))
        batch_op.add_column(sa.Column("request_hash", sa.String(length=64), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("state", sa.String(length=20), nullable=False, server_default="succeeded"))
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))
        batch_op.alter_column("status_code", existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column("response_body", existing_type=sa.Text(), nullable=True)
        batch_op.drop_constraint("uq_idempotency", type_="unique")
        batch_op.create_unique_constraint(
            "uq_idempotency",
            ["tenant_id", "endpoint", "method", "idempotency_key"],
        )
        batch_op.alter_column("method", server_default=None)
        batch_op.alter_column("request_hash", server_default=None)
        batch_op.alter_column("state", server_default=None)

    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.add_column(sa.Column("store_id", GUID(), nullable=True))
        batch_op.add_column(sa.Column("entity_type", sa.String(length=255), nullable=False, server_default="unknown"))
        batch_op.add_column(sa.Column("entity_id", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("result", sa.String(length=50), nullable=False, server_default="success"))
        batch_op.create_index("ix_audit_events_store_id", ["store_id"])
        batch_op.alter_column("entity_type", server_default=None)
        batch_op.alter_column("result", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.drop_index("ix_audit_events_store_id")
        batch_op.drop_column("result")
        batch_op.drop_column("entity_id")
        batch_op.drop_column("entity_type")
        batch_op.drop_column("store_id")

    with op.batch_alter_table("idempotency_records") as batch_op:
        batch_op.drop_constraint("uq_idempotency", type_="unique")
        batch_op.create_unique_constraint("uq_idempotency", ["tenant_id", "endpoint", "idempotency_key"])
        batch_op.alter_column("status_code", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("response_body", existing_type=sa.Text(), nullable=False)
        batch_op.drop_column("updated_at")
        batch_op.drop_column("state")
        batch_op.drop_column("request_hash")
        batch_op.drop_column("method")
