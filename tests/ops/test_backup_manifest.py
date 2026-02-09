import json
from pathlib import Path

from app.ops.backup_utils import sha256_file, validate_manifest


def test_validate_manifest(tmp_path: Path):
    data_file = tmp_path / "tenants.jsonl"
    data_file.write_text("{}", encoding="utf-8")
    manifest = {
        "timestamp": "20240101T000000Z",
        "schema_rev": "rev1",
        "row_counts": {"tenants": 1},
        "files": [{"name": data_file.name, "sha256": sha256_file(data_file), "rows": 1}],
        "core_tables": ["tenants"],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    errors = validate_manifest(manifest, tmp_path)
    assert errors == []
