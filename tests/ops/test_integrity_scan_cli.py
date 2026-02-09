import json
import uuid

from app.aris3.db.models import StockItem, Store, Tenant
from app.ops.integrity_scan import run_scan


def test_integrity_scan_no_findings(db_session, capsys):
    tenant = Tenant(id=uuid.uuid4(), name="Tenant Scan")
    store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name="Store Scan")
    db_session.add_all([tenant, store])
    db_session.commit()

    database_url = str(db_session.get_bind().url)
    exit_code = run_scan(str(tenant.id), "json", False, database_url=database_url)
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["summary"]["critical"] == 0


def test_integrity_scan_critical_exit(db_session, capsys):
    tenant = Tenant(id=uuid.uuid4(), name="Tenant Scan")
    db_session.add(tenant)
    db_session.add(
        StockItem(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            status="SOLD",
            location_code="BODEGA",
            location_is_vendible=True,
        )
    )
    db_session.commit()

    database_url = str(db_session.get_bind().url)
    exit_code = run_scan(str(tenant.id), "json", True, database_url=database_url)
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["summary"]["critical"] >= 1
