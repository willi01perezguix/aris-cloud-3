from datetime import date
from decimal import Decimal

from tests.pos_sales_helpers import create_tenant_user, login, seed_defaults


def test_no_double_count_for_idempotent_cash_in(client, db_session):
    seed_defaults(db_session)
    _tenant, store, _other_store, manager = create_tenant_user(
        db_session, suffix="pos-cash-idem-day2", role="MANAGER"
    )
    token = login(client, manager.username, "Pass1234!")
    business_date = date.today()

    open_session = client.post(
        "/aris3/pos/cash/session/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-open"},
        json={
            "transaction_id": "txn-idem-open",
            "store_id": str(store.id),
            "action": "OPEN",
            "opening_amount": 40.0,
            "business_date": business_date.isoformat(),
            "timezone": "UTC",
        },
    )
    assert open_session.status_code == 200

    cash_in_payload = {
        "transaction_id": "txn-idem-cash-in",
        "store_id": str(store.id),
        "action": "CASH_IN",
        "amount": 10.0,
    }
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-cash-in"}
    first = client.post("/aris3/pos/cash/session/actions", headers=headers, json=cash_in_payload)
    assert first.status_code == 200
    replay = client.post("/aris3/pos/cash/session/actions", headers=headers, json=cash_in_payload)
    assert replay.status_code == 200

    breakdown = client.get(
        "/aris3/pos/cash/reconciliation/breakdown",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store.id), "business_date": business_date.isoformat(), "timezone": "UTC"},
    )
    assert breakdown.status_code == 200
    body = breakdown.json()
    assert Decimal(body["cash_in"]) == Decimal("10.00")
    counts = {row["movement_type"]: row["movement_count"] for row in body["movements"]}
    assert counts["CASH_IN"] == 1
