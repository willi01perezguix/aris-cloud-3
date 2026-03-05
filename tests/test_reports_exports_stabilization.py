from datetime import date

from app.aris3.db.models import ExportRecord
from tests.pos_sales_helpers import create_tenant_user, login, seed_defaults


def test_reports_meta_filters_are_real_and_normalized(client, db_session):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix="reports-meta-filters")
    token = login(client, user.username, "Pass1234!")

    response = client.get(
        "/aris3/reports/overview",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store.id), "from": "2026-03-01", "to": "2026-03-01", "timezone": "UTC"},
    )
    assert response.status_code == 200
    meta = response.json()["meta"]
    assert meta["from_datetime"].startswith("2026-03-01T00:00:00")
    assert meta["to_datetime"].startswith("2026-03-01T23:59:59.999999")
    assert "additionalProp1" not in meta["filters"]
    assert meta["filters"]["store_id"] == str(store.id)


def test_exports_filters_snapshot_stores_real_filters_only(client, db_session):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix="exports-filters-snapshot")
    token = login(client, user.username, "Pass1234!")
    today = date.today().isoformat()

    created = client.post(
        "/aris3/exports",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "snapshot-real-filters"},
        json={
            "source_type": "reports_daily",
            "format": "csv",
            "filters": {"store_id": str(store.id), "from": today, "to": today, "timezone": "UTC"},
            "transaction_id": "txn-snapshot-real-filters",
        },
    )
    assert created.status_code == 201
    payload = created.json()
    assert "additionalProp1" not in payload["filters_snapshot"]
    assert payload["filters_snapshot"]["store_id"] == str(store.id)

    db_record = db_session.get(ExportRecord, payload["export_id"])
    assert "additionalProp1" not in db_record.filters_snapshot


def test_invalid_export_id_yields_flat_422_error(client, db_session):
    seed_defaults(db_session)
    _tenant, _store, _other_store, user = create_tenant_user(db_session, suffix="exports-download-422")
    token = login(client, user.username, "Pass1234!")

    response = client.get("/aris3/exports/not-a-uuid/download", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert isinstance(body.get("details", {}).get("errors"), list)
