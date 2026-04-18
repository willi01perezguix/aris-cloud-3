"""s12 ai preload extractions

Revision ID: 0035_s12_ai_preload_extractions
Revises: 0034_s11_advances_gift_cards_cash_integration
Create Date: 2026-04-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0035_s12_ai_preload_extractions"
down_revision = "0034_s11_advances_gift_cards_cash_integration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stock_ai_extractions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("store_id", sa.String(length=36), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("document_type", sa.String(length=50), nullable=True),
        sa.Column("source_currency", sa.String(length=12), nullable=False),
        sa.Column("exchange_rate_to_gtq", sa.Numeric(12, 4), nullable=True),
        sa.Column("pricing_mode", sa.String(length=30), nullable=False),
        sa.Column("markup_percent", sa.Numeric(12, 4), nullable=True),
        sa.Column("margin_percent", sa.Numeric(12, 4), nullable=True),
        sa.Column("multiplier", sa.Numeric(12, 4), nullable=True),
        sa.Column("rounding_step", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("raw_ai_result", sa.JSON(), nullable=True),
        sa.Column("normalized_result", sa.JSON(), nullable=True),
        sa.Column("warnings", sa.JSON(), nullable=True),
        sa.Column("model_used", sa.String(length=100), nullable=True),
        sa.Column("trace_id", sa.String(length=100), nullable=True),
        sa.Column("preload_session_id", sa.String(length=36), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["preload_session_id"], ["preload_sessions.id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stock_ai_extractions_tenant_id", "stock_ai_extractions", ["tenant_id"])
    op.create_index("ix_stock_ai_extractions_store_id", "stock_ai_extractions", ["store_id"])
    op.create_index("ix_stock_ai_extractions_created_by_user_id", "stock_ai_extractions", ["created_by_user_id"])
    op.create_index("ix_stock_ai_extractions_preload_session_id", "stock_ai_extractions", ["preload_session_id"])

    op.create_table(
        "stock_ai_extraction_files",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("extraction_id", sa.String(length=36), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["extraction_id"], ["stock_ai_extractions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stock_ai_extraction_files_extraction_id", "stock_ai_extraction_files", ["extraction_id"])


def downgrade() -> None:
    op.drop_index("ix_stock_ai_extraction_files_extraction_id", table_name="stock_ai_extraction_files")
    op.drop_table("stock_ai_extraction_files")
    op.drop_index("ix_stock_ai_extractions_preload_session_id", table_name="stock_ai_extractions")
    op.drop_index("ix_stock_ai_extractions_created_by_user_id", table_name="stock_ai_extractions")
    op.drop_index("ix_stock_ai_extractions_store_id", table_name="stock_ai_extractions")
    op.drop_index("ix_stock_ai_extractions_tenant_id", table_name="stock_ai_extractions")
    op.drop_table("stock_ai_extractions")
