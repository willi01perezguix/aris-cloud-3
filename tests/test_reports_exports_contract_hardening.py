from datetime import date
from decimal import Decimal

from app.aris3.db.models import ExportRecord
from tests.pos_sales_helpers import create_tenant_user, login, seed_defaults


MONEY_FIELDS_DAILY = [
    "gross_sales",
    "refunds_total",
    "net_sales",
    "cogs_gross",
    "cogs_reversed_from_returns",
    "net_cogs",
    "net_profit",
    "average_ticket",
]
MONEY_FIELDS_CALENDAR = ["net_sales", "net_profit"]


def _assert_money_is_normalized(value: str) -> None:
    assert isinstance(value, str)
    assert "+" not in value
    assert "E" not in value.upper()
    assert not (value.startswith("0") and value not in {"0", "0.00"} and not value.startswith("0."))
    assert Decimal(value).quantize(Decimal("0.01")) == Decimal(value)


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
    for field in MONEY_FIELDS_DAILY:
        _assert_money_is_normalized(totals[field])


def test_reports_daily_rows_money_are_normalized_and_in_filter_range(client, db_session):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix="reports-daily-rows-money")
    token = login(client, user.username, "Pass1234!")

    response = client.get(
        "/aris3/reports/daily",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store.id), "from": "2026-03-01", "to": "2026-03-03", "timezone": "UTC"},
    )
    assert response.status_code == 200
    payload = response.json()
    business_dates = [row["business_date"] for row in payload["rows"]]
    assert all("2026-03-01" <= d <= "2026-03-03" for d in business_dates)
    for row in payload["rows"]:
        for field in MONEY_FIELDS_DAILY:
            _assert_money_is_normalized(row[field])


def test_reports_calendar_rows_money_are_normalized_and_in_filter_range(client, db_session):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix="reports-calendar-rows-money")
    token = login(client, user.username, "Pass1234!")

    response = client.get(
        "/aris3/reports/calendar",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store.id), "from": "2026-03-01", "to": "2026-03-03", "timezone": "UTC"},
    )
    assert response.status_code == 200
    payload = response.json()
    business_dates = [row["business_date"] for row in payload["rows"]]
    assert all("2026-03-01" <= d <= "2026-03-03" for d in business_dates)
    for row in payload["rows"]:
        for field in MONEY_FIELDS_CALENDAR:
            _assert_money_is_normalized(row[field])


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


def test_export_download_returns_404_when_file_missing(client, db_session):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix="exports-download-missing-file")
    token = login(client, user.username, "Pass1234!")
    today = date.today().isoformat()

    create_response = client.post(
        "/aris3/exports",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "download-missing-file"},
        json={
            "source_type": "reports_daily",
            "format": "csv",
            "filters": {"store_id": str(store.id), "from": today, "to": today, "timezone": "UTC"},
            "transaction_id": "txn-download-missing-file",
        },
    )
    assert create_response.status_code == 201
    export_id = create_response.json()["export_id"]

    db_record = db_session.get(ExportRecord, export_id)
    db_record.file_path = "/tmp/aris3/non-existent-export.csv"
    db_session.commit()

    missing_file = client.get(f"/aris3/exports/{export_id}/download", headers={"Authorization": f"Bearer {token}"})
    assert missing_file.status_code == 404
    assert missing_file.json()["code"] == "RESOURCE_NOT_FOUND"
