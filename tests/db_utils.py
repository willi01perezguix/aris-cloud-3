from __future__ import annotations

import uuid
from collections.abc import Callable

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def create_postgres_test_database(base_url: str) -> tuple[str, Callable[[], None]]:
    url = make_url(base_url)
    db_name = f"test_{uuid.uuid4().hex}"
    admin_url = url.set(database="postgres")

    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", future=True)
    with engine.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    engine.dispose()

    test_url = str(url.set(database=db_name))

    def cleanup() -> None:
        drop_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", future=True)
        with drop_engine.connect() as conn:
            conn.execute(
                text(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = :db_name
                    """
                ),
                {"db_name": db_name},
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))
        drop_engine.dispose()

    return test_url, cleanup
