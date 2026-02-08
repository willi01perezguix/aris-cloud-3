import importlib
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from alembic import command
from alembic.config import Config

from tests.db_utils import create_postgres_test_database


def _setup_app(database_url: str):
    os.environ["DATABASE_URL"] = database_url
    os.environ["SECRET_KEY"] = "test-secret"

    import app.aris3.core.config as config
    import app.aris3.db.session as session
    import app.main as main

    importlib.reload(config)
    importlib.reload(session)
    importlib.reload(main)

    return main.create_app(), session


def _run_migrations(database_url: str):
    os.environ["DATABASE_URL"] = database_url
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


@pytest.fixture()
def client(tmp_path: Path):
    database_url = os.getenv("DATABASE_URL", "")
    cleanup = None

    if database_url.startswith("postgres"):
        database_url, cleanup = create_postgres_test_database(database_url)
    else:
        db_path = tmp_path / "test.db"
        database_url = f"sqlite+pysqlite:///{db_path}"

    _run_migrations(database_url)
    app, session = _setup_app(database_url)

    with TestClient(app) as client:
        yield client

    session.engine.dispose()
    if cleanup:
        cleanup()


@pytest.fixture()
def db_session(client):
    from app.aris3.db.session import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
