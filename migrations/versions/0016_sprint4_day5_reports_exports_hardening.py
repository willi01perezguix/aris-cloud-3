"""sprint4 day5 reports exports hardening

Revision ID: 0016_sprint4_day5_reports_exports_hardening
Revises: 0015_sprint4_day4
Create Date: 2025-02-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0016_sprint4_day5_reports_exports_hardening"
down_revision = "0015_sprint4_day4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("export_records", sa.Column("failure_reason_code", sa.String(length=50), nullable=True))

    op.create_index(
        "ix_export_records_tenant_store_created",
        "export_records",
        ["tenant_id", "store_id", "created_at"],
    )
    op.create_index(
        "ix_export_records_tenant_store_source_format",
        "export_records",
        ["tenant_id", "store_id", "source_type", "format"],
    )
    op.create_index(
        "ix_pos_sales_tenant_store_status_checked",
        "pos_sales",
        ["tenant_id", "store_id", "status", "checked_out_at"],
    )
    op.create_index(
        "ix_pos_return_events_tenant_store_created",
        "pos_return_events",
        ["tenant_id", "store_id", "created_at"],
    )
    op.create_index(
        "ix_pos_payments_tenant_method_sale",
        "pos_payments",
        ["tenant_id", "method", "sale_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_pos_payments_tenant_method_sale", table_name="pos_payments")
    op.drop_index("ix_pos_return_events_tenant_store_created", table_name="pos_return_events")
    op.drop_index("ix_pos_sales_tenant_store_status_checked", table_name="pos_sales")
    op.drop_index("ix_export_records_tenant_store_source_format", table_name="export_records")
    op.drop_index("ix_export_records_tenant_store_created", table_name="export_records")

    op.drop_column("export_records", "failure_reason_code")
