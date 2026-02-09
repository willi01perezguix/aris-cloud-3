from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
import uuid

from sqlalchemy import select, text
from sqlalchemy.engine import Engine

from app.aris3.core.config import settings
from app.aris3.db.base import Base


CORE_TABLES = [
    "tenants",
    "stores",
    "users",
    "stock_items",
    "transfers",
    "transfer_lines",
    "transfer_movements",
    "pos_sales",
    "pos_sale_lines",
    "pos_payments",
    "pos_cash_sessions",
    "pos_cash_movements",
    "pos_cash_day_closes",
    "audit_events",
    "idempotency_records",
]


def safe_slug(value: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9._-]", "_", value)
    return sanitized.strip("._-") or "artifact"


def ensure_artifacts_dir() -> Path:
    base = Path(settings.OPS_ARTIFACTS_DIR)
    base.mkdir(parents=True, exist_ok=True)
    return base


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def dump_table_to_jsonl(db, table_name: str, output_dir: Path) -> tuple[int, Path]:
    table = Base.metadata.tables[table_name]
    rows = db.execute(select(table)).mappings().all()
    file_path = output_dir / f"{safe_slug(table_name)}.jsonl"
    with file_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(_serialize_row(dict(row))) + "\n")
    return len(rows), file_path


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    serialized = {}
    for key, value in row.items():
        if isinstance(value, (datetime, date)):
            serialized[key] = value.isoformat()
        elif isinstance(value, uuid.UUID):
            serialized[key] = str(value)
        else:
            serialized[key] = value
    return serialized


def parse_value(value: Any, column) -> Any:
    if value is None:
        return None
    try:
        python_type = column.type.python_type
    except Exception:
        return value
    if python_type is datetime and isinstance(value, str):
        return datetime.fromisoformat(value)
    if python_type is date and isinstance(value, str):
        return date.fromisoformat(value)
    if python_type is uuid.UUID and isinstance(value, str):
        return uuid.UUID(value)
    return value


def load_table_from_jsonl(db, table_name: str, input_path: Path) -> int:
    table = Base.metadata.tables[table_name]
    rows = []
    with input_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            raw = json.loads(line)
            parsed = {col.name: parse_value(raw.get(col.name), col) for col in table.columns}
            rows.append(parsed)
    if rows:
        db.execute(table.insert(), rows)
    return len(rows)


def get_schema_revision(engine: Engine) -> str | None:
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            row = result.first()
            return row[0] if row else None
    except Exception:
        return None


@dataclass
class ManifestFile:
    name: str
    sha256: str
    rows: int


def validate_manifest(manifest: dict, base_dir: Path) -> list[str]:
    errors: list[str] = []
    for field in ("timestamp", "schema_rev", "row_counts", "files", "core_tables"):
        if field not in manifest:
            errors.append(f"missing_field:{field}")
    files = manifest.get("files", [])
    for entry in files:
        name = entry.get("name")
        if not name:
            errors.append("file_missing_name")
            continue
        path = base_dir / name
        if not path.exists():
            errors.append(f"file_missing:{name}")
            continue
        checksum = entry.get("sha256")
        if checksum and checksum != sha256_file(path):
            errors.append(f"checksum_mismatch:{name}")
    return errors
