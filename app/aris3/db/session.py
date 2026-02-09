import time

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.aris3.core.config import settings
from app.aris3.core.db_timing import add_db_time, get_db_time_ms

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.DATABASE_URL, echo=False, future=True, connect_args=connect_args)


@event.listens_for(engine, "before_cursor_execute")
def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    if get_db_time_ms() is None:
        return
    conn.info["query_start_time"] = time.perf_counter()


@event.listens_for(engine, "after_cursor_execute")
def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    if get_db_time_ms() is None:
        return
    start = conn.info.pop("query_start_time", None)
    if start is None:
        return
    add_db_time((time.perf_counter() - start) * 1000)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
