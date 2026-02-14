import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import Store, Tenant, User


def _make_user(*, tenant_id, store_id, username):
    return User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        store_id=store_id,
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="USER",
        status="active",
        must_change_password=False,
        is_active=True,
    )


def test_user_with_store_from_same_tenant_is_valid(db_session):
    tenant = Tenant(id=uuid.uuid4(), name="tenant-valid")
    store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name="store-valid")

    db_session.add_all([tenant, store])
    db_session.commit()

    user = _make_user(tenant_id=tenant.id, store_id=store.id, username="aligned-user")
    db_session.add(user)
    db_session.commit()

    saved = db_session.get(User, user.id)
    assert saved is not None
    assert saved.tenant_id == tenant.id
    assert saved.store_id == store.id


def test_user_with_store_from_other_tenant_fails(db_session):
    if db_session.bind.dialect.name == "sqlite":
        db_session.execute(text("PRAGMA foreign_keys=ON"))

    tenant_a = Tenant(id=uuid.uuid4(), name="tenant-a-mismatch")
    tenant_b = Tenant(id=uuid.uuid4(), name="tenant-b-mismatch")
    store_b = Store(id=uuid.uuid4(), tenant_id=tenant_b.id, name="store-b-mismatch")

    db_session.add_all([tenant_a, tenant_b, store_b])
    db_session.commit()

    db_session.add(_make_user(tenant_id=tenant_a.id, store_id=store_b.id, username="mismatch-user"))

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_migration_upgrade_downgrade_roundtrip(tmp_path: Path):
    db_path = tmp_path / "roundtrip.db"
    database_url = f"sqlite+pysqlite:///{db_path}"

    os.environ["DATABASE_URL"] = database_url
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "0016_s4d5_reports_exports_hard")
    command.upgrade(alembic_cfg, "head")
