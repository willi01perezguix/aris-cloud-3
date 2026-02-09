from datetime import date

from tests.pos_sales_helpers import create_tenant_user, login, seed_defaults


def test_reports_observability_fields_present(client, db_session):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix="reports-day5-obs")
    token = login(client, user.username, "Pass1234!")

    today = date.today().isoformat()
    response = client.get(
        "/aris3/reports/overview",
        headers={"Authorization": f"Bearer {token}", "X-Trace-ID": "trace-obs-1"},
        params={"store_id": str(store.id), "from": today, "to": today, "timezone": "UTC"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["trace_id"] == "trace-obs-1"
    assert payload["meta"]["query_ms"] >= 0
    assert payload["meta"]["filters"]["store_id"] == str(store.id)


def test_exports_observability_fields_present(client, db_session):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix="exports-day5-obs")
    token = login(client, user.username, "Pass1234!")

    today = date.today().isoformat()
    response = client.post(
        "/aris3/exports",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "export-obs", "X-Trace-ID": "trace-obs-2"},
        json={
            "source_type": "reports_overview",
            "format": "csv",
            "filters": {"store_id": str(store.id), "from": today, "to": today, "timezone": "UTC"},
            "transaction_id": "txn-export-obs",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["trace_id"] == "trace-obs-2"
    assert payload["filters_snapshot"]["store_id"] == str(store.id)
    assert payload["content_type"] == "text/csv"
