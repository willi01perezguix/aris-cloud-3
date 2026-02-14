"""sprint4 day6 tenant store user hardening

Revision ID: 0017_s4d6_tenant_store_user_hard
Revises: 0016_s4d5_reports_exports_hard
Create Date: 2025-02-15 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0017_s4d6_tenant_store_user_hard"
down_revision = "0016_s4d5_reports_exports_hard"
branch_labels = None
depends_on = None


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _constraint_names(inspector: sa.Inspector, table_name: str, *, ctype: str) -> set[str]:
    if ctype == "unique":
        return {c["name"] for c in inspector.get_unique_constraints(table_name) if c.get("name")}
    if ctype == "foreignkey":
        return {c["name"] for c in inspector.get_foreign_keys(table_name) if c.get("name")}
    raise ValueError(f"Unsupported constraint type: {ctype}")


def _assert_preconditions(bind: sa.Connection) -> None:
    checks = {
        "stores.tenant_id contains NULL values": "SELECT COUNT(*) FROM stores WHERE tenant_id IS NULL",
        "stores.tenant_id references missing tenant": """
            SELECT COUNT(*)
            FROM stores s
            LEFT JOIN tenants t ON t.id = s.tenant_id
            WHERE s.tenant_id IS NOT NULL AND t.id IS NULL
        """,
        "users.tenant_id contains NULL values": "SELECT COUNT(*) FROM users WHERE tenant_id IS NULL",
        "users.tenant_id references missing tenant": """
            SELECT COUNT(*)
            FROM users u
            LEFT JOIN tenants t ON t.id = u.tenant_id
            WHERE u.tenant_id IS NOT NULL AND t.id IS NULL
        """,
        "users.store_id references missing store": """
            SELECT COUNT(*)
            FROM users u
            LEFT JOIN stores s ON s.id = u.store_id
            WHERE u.store_id IS NOT NULL AND s.id IS NULL
        """,
        "users has cross-tenant store assignment": """
            SELECT COUNT(*)
            FROM users u
            JOIN stores s ON s.id = u.store_id
            WHERE u.store_id IS NOT NULL AND u.tenant_id <> s.tenant_id
        """,
    }

    for message, sql in checks.items():
        count = bind.execute(sa.text(sql)).scalar_one()
        if count:
            raise RuntimeError(
                "Precondition failed before applying tenant/store/user hardening: "
                f"{message} (rows={count})."
            )


def _create_postgres_trigger(bind: sa.Connection) -> None:
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION validate_user_tenant_store_consistency()
            RETURNS TRIGGER
            LANGUAGE plpgsql
            AS $$
            BEGIN
                IF NEW.store_id IS NULL THEN
                    RETURN NEW;
                END IF;

                IF NOT EXISTS (
                    SELECT 1
                    FROM stores s
                    WHERE s.id = NEW.store_id
                      AND s.tenant_id = NEW.tenant_id
                ) THEN
                    RAISE EXCEPTION 'TENANT_STORE_MISMATCH'
                    USING ERRCODE = '23514',
                          DETAIL = 'users.tenant_id must match stores.tenant_id when users.store_id is set';
                END IF;

                RETURN NEW;
            END;
            $$;
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_users_tenant_store_consistency
            BEFORE INSERT OR UPDATE OF tenant_id, store_id ON users
            FOR EACH ROW
            EXECUTE FUNCTION validate_user_tenant_store_consistency();
            """
        )
    )


def _drop_postgres_trigger(bind: sa.Connection) -> None:
    if bind.dialect.name != "postgresql":
        return

    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_users_tenant_store_consistency ON users"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS validate_user_tenant_store_consistency()"))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    _assert_preconditions(bind)

    user_columns = _column_names(inspector, "users")
    store_columns = _column_names(inspector, "stores")
    user_fk_names = _constraint_names(inspector, "users", ctype="foreignkey")
    store_unique_names = _constraint_names(inspector, "stores", ctype="unique")
    user_index_names = _index_names(inspector, "users")
    store_index_names = _index_names(inspector, "stores")

    with op.batch_alter_table("stores") as batch_op:
        if "tenant_id" in store_columns:
            batch_op.alter_column("tenant_id", nullable=False)

        if "uq_store_tenant_name" not in store_unique_names and "name" in store_columns:
            batch_op.create_unique_constraint("uq_store_tenant_name", ["tenant_id", "name"])

        if "uq_stores_tenant_id_id" not in store_unique_names:
            batch_op.create_unique_constraint("uq_stores_tenant_id_id", ["tenant_id", "id"])

        if "code" in store_columns and "uq_stores_tenant_code" not in store_unique_names:
            batch_op.create_unique_constraint("uq_stores_tenant_code", ["tenant_id", "code"])

    with op.batch_alter_table("users") as batch_op:
        if "tenant_id" in user_columns:
            batch_op.alter_column("tenant_id", nullable=False)

        if "fk_users_store_id" in user_fk_names:
            batch_op.drop_constraint("fk_users_store_id", type_="foreignkey")

        batch_op.create_foreign_key("fk_users_store_id", "stores", ["store_id"], ["id"])

        if "fk_users_tenant_store" not in user_fk_names:
            batch_op.create_foreign_key(
                "fk_users_tenant_store",
                "stores",
                ["tenant_id", "store_id"],
                ["tenant_id", "id"],
            )

    if "ix_users_tenant_id" not in user_index_names:
        op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    if "ix_users_store_id" not in user_index_names:
        op.create_index("ix_users_store_id", "users", ["store_id"])
    if "ix_stores_tenant_id" not in store_index_names:
        op.create_index("ix_stores_tenant_id", "stores", ["tenant_id"])

    _create_postgres_trigger(bind)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    _drop_postgres_trigger(bind)

    user_fk_names = _constraint_names(inspector, "users", ctype="foreignkey")
    store_unique_names = _constraint_names(inspector, "stores", ctype="unique")
    user_index_names = _index_names(inspector, "users")
    store_index_names = _index_names(inspector, "stores")

    if "ix_users_tenant_id" in user_index_names:
        op.drop_index("ix_users_tenant_id", table_name="users")
    if "ix_users_store_id" in user_index_names:
        op.drop_index("ix_users_store_id", table_name="users")
    if "ix_stores_tenant_id" in store_index_names:
        op.drop_index("ix_stores_tenant_id", table_name="stores")

    with op.batch_alter_table("users") as batch_op:
        if "fk_users_tenant_store" in user_fk_names:
            batch_op.drop_constraint("fk_users_tenant_store", type_="foreignkey")

    with op.batch_alter_table("stores") as batch_op:
        if "uq_stores_tenant_id_id" in store_unique_names:
            batch_op.drop_constraint("uq_stores_tenant_id_id", type_="unique")

        if "uq_stores_tenant_code" in store_unique_names:
            batch_op.drop_constraint("uq_stores_tenant_code", type_="unique")
