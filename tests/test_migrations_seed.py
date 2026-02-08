import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import sessionmaker

from app.aris3.db.models import PermissionCatalog, RoleTemplate, RoleTemplatePermission, User
from app.aris3.db.seed import run_seed


def _run_migrations(database_url: str):
    os.environ["DATABASE_URL"] = database_url
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def test_migrations_apply(tmp_path: Path):
    db_path = tmp_path / "migrations.db"
    database_url = f"sqlite+pysqlite:///{db_path}"
    _run_migrations(database_url)

    engine = create_engine(database_url, future=True)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    assert "tenants" in tables
    assert "stores" in tables
    assert "users" in tables
    assert "permission_catalog" in tables
    assert "role_templates" in tables
    assert "role_template_permissions" in tables
    assert "idempotency_records" in tables
    assert "audit_events" in tables

    indexes = [index["name"] for index in inspector.get_indexes("audit_events")]
    assert indexes.count("ix_audit_events_trace_id") == 1


def test_seed_is_idempotent(tmp_path: Path):
    db_path = tmp_path / "seed.db"
    database_url = f"sqlite+pysqlite:///{db_path}"
    _run_migrations(database_url)

    engine = create_engine(database_url, future=True)
    SessionLocal = sessionmaker(bind=engine, future=True)

    with SessionLocal() as db:
        run_seed(db)
        permissions_count = db.scalar(select(func.count()).select_from(PermissionCatalog))
        roles_count = db.scalar(select(func.count()).select_from(RoleTemplate))
        mapping_count = db.scalar(select(func.count()).select_from(RoleTemplatePermission))
        users_count = db.scalar(select(func.count()).select_from(User))

        run_seed(db)
        permissions_count_after = db.scalar(select(func.count()).select_from(PermissionCatalog))
        roles_count_after = db.scalar(select(func.count()).select_from(RoleTemplate))
        mapping_count_after = db.scalar(select(func.count()).select_from(RoleTemplatePermission))
        users_count_after = db.scalar(select(func.count()).select_from(User))

        assert permissions_count_after == permissions_count
        assert roles_count_after == roles_count
        assert mapping_count_after == mapping_count
        assert users_count_after == users_count

        assert (
            db.scalar(select(func.count()).select_from(RoleTemplate).where(RoleTemplate.name == "SUPERADMIN"))
            == 1
        )
        assert (
            db.scalar(
                select(func.count()).select_from(PermissionCatalog).where(PermissionCatalog.code == "TENANT_VIEW")
            )
            == 1
        )
