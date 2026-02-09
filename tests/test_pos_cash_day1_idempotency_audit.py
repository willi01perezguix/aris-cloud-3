from datetime import date

from app.aris3.core.error_catalog import ErrorCatalog
from app.aris3.db.models import AuditEvent
from tests.pos_sales_helpers import create_tenant_user, login, seed_defaults


def test_pos_cash_idempotency_and_audit(client, db_session):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix="pos-cash-idem")
    token = login(client, user.username, "Pass1234!")

    open_payload = {
        "transaction_id": "txn-open-idem",
        "store_id": str(store.id),
        "action": "OPEN",
        "opening_amount": 100.0,
        "business_date": date.today().isoformat(),
        "timezone": "UTC",
    }
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "cash-open-idem"}
    first = client.post("/aris3/pos/cash/session/actions", headers=headers, json=open_payload)
    assert first.status_code == 200

    replay = client.post("/aris3/pos/cash/session/actions", headers=headers, json=open_payload)
    assert replay.status_code == 200
    assert replay.json() == first.json()
    assert replay.headers.get("X-Idempotency-Result") == ErrorCatalog.IDEMPOTENCY_REPLAY.code

    conflict = client.post(
        "/aris3/pos/cash/session/actions",
        headers=headers,
        json={**open_payload, "transaction_id": "txn-open-idem-2", "opening_amount": 120.0},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == ErrorCatalog.IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD.code

    cash_in_payload = {
        "transaction_id": "txn-cash-in-idem",
        "store_id": str(store.id),
        "action": "CASH_IN",
        "amount": 15.0,
    }
    cash_in_headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "cash-in-idem"}
    cash_in = client.post("/aris3/pos/cash/session/actions", headers=cash_in_headers, json=cash_in_payload)
    assert cash_in.status_code == 200
    cash_in_replay = client.post("/aris3/pos/cash/session/actions", headers=cash_in_headers, json=cash_in_payload)
    assert cash_in_replay.status_code == 200
    cash_in_conflict = client.post(
        "/aris3/pos/cash/session/actions",
        headers=cash_in_headers,
        json={**cash_in_payload, "transaction_id": "txn-cash-in-idem-2", "amount": 20.0},
    )
    assert cash_in_conflict.status_code == 409

    cash_out_payload = {
        "transaction_id": "txn-cash-out-idem",
        "store_id": str(store.id),
        "action": "CASH_OUT",
        "amount": 10.0,
    }
    cash_out_headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "cash-out-idem"}
    cash_out = client.post("/aris3/pos/cash/session/actions", headers=cash_out_headers, json=cash_out_payload)
    assert cash_out.status_code == 200
    cash_out_replay = client.post("/aris3/pos/cash/session/actions", headers=cash_out_headers, json=cash_out_payload)
    assert cash_out_replay.status_code == 200
    cash_out_conflict = client.post(
        "/aris3/pos/cash/session/actions",
        headers=cash_out_headers,
        json={**cash_out_payload, "transaction_id": "txn-cash-out-idem-2", "amount": 5.0},
    )
    assert cash_out_conflict.status_code == 409

    close_payload = {
        "transaction_id": "txn-close-idem",
        "store_id": str(store.id),
        "action": "CLOSE",
        "counted_cash": 105.0,
    }
    close_headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "cash-close-idem"}
    close = client.post("/aris3/pos/cash/session/actions", headers=close_headers, json=close_payload)
    assert close.status_code == 200
    close_replay = client.post("/aris3/pos/cash/session/actions", headers=close_headers, json=close_payload)
    assert close_replay.status_code == 200
    close_conflict = client.post(
        "/aris3/pos/cash/session/actions",
        headers=close_headers,
        json={**close_payload, "transaction_id": "txn-close-idem-2", "counted_cash": 106.0},
    )
    assert close_conflict.status_code == 409

    day_close_payload = {
        "transaction_id": "txn-day-close-idem",
        "store_id": str(store.id),
        "action": "CLOSE_DAY",
        "business_date": date.today().isoformat(),
        "timezone": "UTC",
    }
    day_close_headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "day-close-idem"}
    day_close = client.post("/aris3/pos/cash/day-close/actions", headers=day_close_headers, json=day_close_payload)
    assert day_close.status_code == 200
    day_close_replay = client.post("/aris3/pos/cash/day-close/actions", headers=day_close_headers, json=day_close_payload)
    assert day_close_replay.status_code == 200
    assert day_close_replay.headers.get("X-Idempotency-Result") == ErrorCatalog.IDEMPOTENCY_REPLAY.code
    day_close_conflict = client.post(
        "/aris3/pos/cash/day-close/actions",
        headers=day_close_headers,
        json={**day_close_payload, "transaction_id": "txn-day-close-idem-2"},
    )
    assert day_close_conflict.status_code == 409

    session_audit = db_session.query(AuditEvent).filter(AuditEvent.action == "pos_cash_session.open").first()
    assert session_audit is not None
    day_close_audit = db_session.query(AuditEvent).filter(AuditEvent.action == "pos_cash_day_close.close").first()
    assert day_close_audit is not None
