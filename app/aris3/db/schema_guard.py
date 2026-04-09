from __future__ import annotations

import logging

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.aris3.core.config import settings
from app.aris3.db.session import engine

logger = logging.getLogger(__name__)


def verify_schema_alignment() -> None:
    if not settings.SCHEMA_DRIFT_GUARD_ENABLED:
        logger.warning("schema drift guard disabled by SCHEMA_DRIFT_GUARD_ENABLED=false")
        return

    if settings.DATABASE_URL.startswith("sqlite"):
        logger.info("schema drift guard skipped for sqlite database")
        return

    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()
    if len(heads) != 1:
        _handle_guard_failure(f"Expected exactly one Alembic head in code, found {len(heads)}: {heads}")
        return

    expected_head = heads[0]

    try:
        with engine.connect() as conn:
            db_revisions = conn.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
    except SQLAlchemyError as exc:
        _handle_guard_failure(f"Unable to read alembic_version from runtime DB: {exc}")
        return

    if len(db_revisions) != 1:
        _handle_guard_failure(f"Expected single alembic_version row, found {len(db_revisions)}: {db_revisions}")
        return

    current_rev = db_revisions[0]
    if current_rev != expected_head:
        _handle_guard_failure(
            "Schema drift detected: runtime DB revision does not match code head "
            f"(db={current_rev}, code={expected_head})."
        )
        return

    logger.info("schema drift guard passed: runtime DB matches alembic head %s", expected_head)



def _handle_guard_failure(message: str) -> None:
    if settings.SCHEMA_DRIFT_GUARD_ENFORCE:
        raise RuntimeError(message)
    logger.error(message)
