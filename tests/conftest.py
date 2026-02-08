import importlib
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


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


@pytest.fixture()
def client(tmp_path: Path):
    db_path = tmp_path / "test.db"
    app, session = _setup_app(f"sqlite+pysqlite:///{db_path}")

    from app.aris3.db.models import Base

    Base.metadata.create_all(bind=session.engine)

    with TestClient(app) as client:
        yield client


@pytest.fixture()
def db_session(client):
    from app.aris3.db.session import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
