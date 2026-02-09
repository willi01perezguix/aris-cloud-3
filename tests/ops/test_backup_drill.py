from pathlib import Path

from app.aris3.core.config import settings
from app.aris3.db.models import Tenant
from scripts.ops.backup_create import run_backup
from scripts.ops.backup_restore_verify import run_restore_verify


def test_backup_manifest_lifecycle(db_session, tmp_path: Path):
    settings.OPS_ARTIFACTS_DIR = str(tmp_path)
    settings.OPS_DRILL_TIMEOUT_SEC = 5
    tenant = Tenant(name="Tenant Backup")
    db_session.add(tenant)
    db_session.commit()

    database_url = str(db_session.get_bind().url)
    manifest_path = run_backup("test_backup", database_url=database_url)
    assert manifest_path.exists()

    report_path = run_restore_verify(manifest_path, database_url=database_url)
    assert report_path.exists()
