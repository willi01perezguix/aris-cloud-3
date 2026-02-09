from datetime import date, timedelta

from app.aris3.core.config import settings
from app.aris3.db.models import ExportRecord
from tests.pos_sales_helpers import create_tenant_user, login, seed_defaults


def test_exports_max_rows_limit_sets_failed_reason(client, db_session, monkeypatch):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix="exports-day5-limit")
    token = login(client, user.username, "Pass1234!")

    monkeypatch.setattr(settings, "REPORTS_MAX_DATE_RANGE_DAYS", 10)
    monkeypatch.setattr(settings, "EXPORTS_MAX_ROWS", 2)

    start = date.today()
    end = start + timedelta(days=2)
    payload = {
        "source_type": "reports_daily",
        "format": "csv",
        "filters": {
            "store_id": str(store.id),
            "from": start.isoformat(),
            "to": end.isoformat(),
            "timezone": "UTC",
        },
        "transaction_id": "txn-export-limit",
    }
    response = client.post(
        "/aris3/exports",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "export-limit"},
        json=payload,
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == "VALIDATION_ERROR"
    assert payload["details"]["reason_code"] == "EXPORT_ROWS_LIMIT_EXCEEDED"

    record = db_session.query(ExportRecord).order_by(ExportRecord.created_at.desc()).first()
    assert record is not None
    assert record.status == "FAILED"
    assert record.failure_reason_code == "EXPORT_ROWS_LIMIT_EXCEEDED"


def test_exports_ready_has_checksum_filesize_content_type(client, db_session, monkeypatch):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix="exports-day5-ready")
    token = login(client, user.username, "Pass1234!")

    monkeypatch.setattr(settings, "EXPORTS_MAX_ROWS", 10)
    monkeypatch.setattr(settings, "REPORTS_MAX_DATE_RANGE_DAYS", 10)

    today = date.today().isoformat()
    payload = {
        "source_type": "reports_overview",
        "format": "csv",
        "filters": {"store_id": str(store.id), "from": today, "to": today, "timezone": "UTC"},
        "transaction_id": "txn-export-ready",
    }
    response = client.post(
        "/aris3/exports",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "export-ready"},
        json=payload,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "READY"
    assert data["checksum_sha256"]
    assert data["file_size_bytes"]
    assert data["content_type"] == "text/csv"
