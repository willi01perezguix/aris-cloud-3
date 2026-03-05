from datetime import date
from decimal import Decimal

from app.aris3.db.models import ExportRecord
from tests.pos_sales_helpers import create_tenant_user, login, seed_defaults


def test_reports_money_fields_are_normalized_strings(client, db_session):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix="reports-money-norm")
    token = login(client, user.username, "Pass1234!")
    today = date.today().isoformat()

    response = client.get(
        "/aris3/reports/overview",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store.id), "from": today, "to": today, "timezone": "UTC"},
    )
    assert response.status_code == 200
    totals = response.json()["totals"]
    money_fields = [
        "gross_sales",
        "refunds_total",
        "net_sales",
        "cogs_gross",
        "cogs_reversed_from_returns",
        "net_cogs",
        "net_profit",
        "average_ticket",
    ]
    for field in money_fields:
        value = totals[field]
        assert isinstance(value, str)
        assert "+" not in value
        assert "E" not in value.upper()
        assert Decimal(value).quantize(Decimal("0.01")) == Decimal(value)


def test_exports_rejects_unknown_source_type_and_flat_422_shape(client, db_session):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix="exports-source-422")
    token = login(client, user.username, "Pass1234!")
    today = date.today().isoformat()

    response = client.post(
        "/aris3/exports",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "bad-source-type"},
        json={
            "source_type": "unknown",
            "format": "csv",
            "filters": {"store_id": str(store.id), "from": today, "to": today, "timezone": "UTC"},
            "transaction_id": "txn-bad-source",
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert isinstance(body.get("details", {}).get("errors"), list)


def test_reports_date_range_validation_error_shape(client, db_session):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix="reports-bad-range")
    token = login(client, user.username, "Pass1234!")

    response = client.get(
        "/aris3/reports/daily",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "store_id": str(store.id),
            "from": "2026-03-05T00:00:00+00:00",
            "to": "2026-03-01T00:00:00+00:00",
            "timezone": "UTC",
        },
    )
    assert response.status_code == 422
    error = response.json()["details"]["errors"][0]
    assert error["field"] == "to"


def test_export_download_returns_binary_headers_and_conflict_when_not_ready(client, db_session):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix="exports-download-contract")
    token = login(client, user.username, "Pass1234!")
    today = date.today().isoformat()

    create_response = client.post(
        "/aris3/exports",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "download-ready"},
        json={
            "source_type": "reports_daily",
            "format": "csv",
            "filters": {"store_id": str(store.id), "from": today, "to": today, "timezone": "UTC"},
            "transaction_id": "txn-download-ready",
        },
    )
    assert create_response.status_code == 201
    export_id = create_response.json()["export_id"]

    download = client.get(f"/aris3/exports/{export_id}/download", headers={"Authorization": f"Bearer {token}"})
    assert download.status_code == 200
    assert "attachment;" in download.headers.get("content-disposition", "")
    assert download.headers.get("content-type", "").startswith("text/csv")

    db_record = db_session.get(ExportRecord, export_id)
    db_record.status = "CREATED"
    db_session.commit()

    not_ready = client.get(f"/aris3/exports/{export_id}/download", headers={"Authorization": f"Bearer {token}"})
    assert not_ready.status_code == 409
    assert not_ready.json()["code"] == "BUSINESS_CONFLICT"
