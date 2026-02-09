from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.aris3.core.config import settings
from app.aris3.db.base import Base
from app.aris3.services.audit import AuditEventPayload, AuditService
from app.ops.backup_utils import (
    CORE_TABLES,
    ensure_artifacts_dir,
    load_table_from_jsonl,
    safe_slug,
    validate_manifest,
)
from app.aris3.db.models import Tenant


def _ensure_timeout(start: float) -> None:
    timeout = settings.OPS_DRILL_TIMEOUT_SEC
    if timeout and (time.monotonic() - start) > timeout:
        raise TimeoutError("backup_restore_verify timed out")


def _resolve_audit_tenant(db) -> str | None:
    tenant_row = db.execute(select(Tenant.id)).first()
    return str(tenant_row[0]) if tenant_row else None


def run_restore_verify(manifest_path: Path, *, database_url: str | None = None) -> Path:
    if not settings.OPS_ENABLE_BACKUP_DRILL:
        raise RuntimeError("Backup drill disabled by OPS_ENABLE_BACKUP_DRILL.")
    start = time.monotonic()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    backup_dir = manifest_path.parent
    errors = validate_manifest(manifest, backup_dir)
    if errors:
        raise ValueError(f"manifest validation failed: {errors}")

    artifacts_dir = ensure_artifacts_dir()
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    restore_db_path = artifacts_dir / f"{safe_slug('restore_verify_' + timestamp)}.db"
    restore_engine = create_engine(f"sqlite+pysqlite:///{restore_db_path}", future=True)
    Base.metadata.create_all(restore_engine)

    row_counts = {}
    with Session(restore_engine) as temp_db:
        for table in CORE_TABLES:
            _ensure_timeout(start)
            file_name = f"{safe_slug(table)}.jsonl"
            file_path = backup_dir / file_name
            inserted = load_table_from_jsonl(temp_db, table, file_path)
            row_counts[table] = inserted
        temp_db.commit()

    expected_counts = manifest.get("row_counts", {})
    comparison = {
        table: {"expected": expected_counts.get(table, 0), "actual": row_counts.get(table, 0)}
        for table in CORE_TABLES
    }
    row_counts_match = all(item["expected"] == item["actual"] for item in comparison.values())
    sanity_checks = _run_sanity_checks(restore_engine)
    status = "PASS" if row_counts_match and sanity_checks["primary_keys_non_null"] else "FAIL"

    report = {
        "timestamp": timestamp,
        "manifest_path": str(manifest_path),
        "restore_db_path": str(restore_db_path),
        "row_counts": comparison,
        "row_counts_match": row_counts_match,
        "sanity_checks": sanity_checks,
        "status": status,
    }
    report_path = artifacts_dir / f"drill_report_{timestamp}.json"
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    audit_engine = create_engine(database_url or settings.DATABASE_URL, future=True)
    SessionLocal = sessionmaker(bind=audit_engine, autoflush=False, autocommit=False, future=True)
    with SessionLocal() as db:
        audit_tenant = _resolve_audit_tenant(db)
        if audit_tenant:
            AuditService(db).record_event(
                AuditEventPayload(
                    tenant_id=audit_tenant,
                    user_id=None,
                    store_id=None,
                    trace_id=None,
                    actor="ops",
                    action="backup.restore_verify",
                    entity_type="backup",
                    entity_id=manifest_path.name,
                    before=None,
                    after={"report": report},
                    metadata={"status": status},
                    result="success" if status == "PASS" else "failure",
                )
            )

    return report_path


def _run_sanity_checks(engine) -> dict:
    checks = {"primary_keys_non_null": True}
    with engine.connect() as conn:
        for table_name in CORE_TABLES:
            table = Base.metadata.tables[table_name]
            for column in table.primary_key.columns:
                count = conn.execute(
                    select(table.c[column.name]).where(table.c[column.name].is_(None))
                ).fetchall()
                if count:
                    checks["primary_keys_non_null"] = False
                    return checks
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Restore/verify backup artifacts for ARIS3")
    parser.add_argument("manifest", help="Path to manifest.json")
    args = parser.parse_args(argv)
    try:
        report_path = run_restore_verify(Path(args.manifest))
        print(str(report_path))
        return 0
    except Exception as exc:
        print(f"backup_restore_verify failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
