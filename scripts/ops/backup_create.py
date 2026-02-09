from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.aris3.core.config import settings
from app.aris3.services.audit import AuditEventPayload, AuditService
from app.ops.backup_utils import CORE_TABLES, ensure_artifacts_dir, dump_table_to_jsonl, get_schema_revision, safe_slug
from app.aris3.db.models import Tenant


def _ensure_timeout(start: float) -> None:
    timeout = settings.OPS_DRILL_TIMEOUT_SEC
    if timeout and (time.monotonic() - start) > timeout:
        raise TimeoutError("backup_create timed out")


def _resolve_audit_tenant(db) -> str | None:
    tenant_row = db.execute(select(Tenant.id)).first()
    return str(tenant_row[0]) if tenant_row else None


def run_backup(output_name: str | None = None, *, database_url: str | None = None) -> Path:
    if not settings.OPS_ENABLE_BACKUP_DRILL:
        raise RuntimeError("Backup drill disabled by OPS_ENABLE_BACKUP_DRILL.")
    start = time.monotonic()
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    base_dir = ensure_artifacts_dir()
    target_name = safe_slug(output_name or f"backup_{timestamp}")
    backup_dir = base_dir / target_name
    backup_dir.mkdir(parents=True, exist_ok=True)

    engine = create_engine(database_url or settings.DATABASE_URL, future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    manifest = {
        "timestamp": timestamp,
        "schema_rev": get_schema_revision(engine),
        "row_counts": {},
        "files": [],
        "core_tables": CORE_TABLES,
    }
    with SessionLocal() as db:
        for table in CORE_TABLES:
            _ensure_timeout(start)
            rows, file_path = dump_table_to_jsonl(db, table, backup_dir)
            manifest["row_counts"][table] = rows
            manifest["files"].append(
                {
                    "name": file_path.name,
                    "sha256": _sha256(file_path),
                    "rows": rows,
                }
            )
        audit_tenant = _resolve_audit_tenant(db)
        if audit_tenant:
            AuditService(db).record_event(
                AuditEventPayload(
                    tenant_id=audit_tenant,
                    user_id=None,
                    store_id=None,
                    trace_id=None,
                    actor="ops",
                    action="backup.create",
                    entity_type="backup",
                    entity_id=target_name,
                    before=None,
                    after={"manifest": manifest},
                    metadata={"timestamp": timestamp},
                    result="success",
                )
            )

    manifest_path = backup_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    return manifest_path


def _sha256(path: Path) -> str:
    import hashlib

    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create backup artifacts for ARIS3")
    parser.add_argument("--name", help="Backup name (directory under artifacts)")
    args = parser.parse_args(argv)
    try:
        manifest_path = run_backup(args.name)
        print(str(manifest_path))
        return 0
    except Exception as exc:
        print(f"backup_create failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
