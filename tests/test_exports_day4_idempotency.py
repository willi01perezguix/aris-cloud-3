from datetime import date

from tests.pos_sales_helpers import create_tenant_user, login, seed_defaults


def test_exports_idempotency_replay_and_conflict(client, db_session):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix="exports-idem")
    token = login(client, user.username, "Pass1234!")
    today = date.today().isoformat()
    payload = {
        "source_type": "reports_daily",
        "format": "csv",
        "filters": {"store_id": str(store.id), "from": today, "to": today, "timezone": "UTC"},
        "transaction_id": "txn-idem-1",
    }
    response = client.post(
        "/aris3/exports",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-exports"},
        json=payload,
    )
    assert response.status_code == 201
    export_id = response.json()["export_id"]

    replay = client.post(
        "/aris3/exports",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-exports"},
        json=payload,
    )
    assert replay.status_code == 201
    assert replay.headers.get("X-Idempotency-Result") == "IDEMPOTENCY_REPLAY"
    assert replay.json()["export_id"] == export_id

    conflict = client.post(
        "/aris3/exports",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-exports"},
        json={
            **payload,
            "format": "pdf",
            "transaction_id": "txn-idem-2",
        },
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"
