from datetime import date

from app.aris3.core.error_catalog import ErrorCatalog
from tests.pos_sales_helpers import create_tenant_user, login, seed_defaults


def test_close_computes_difference_and_immutability(client, db_session):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix="pos-cash-close")
    token = login(client, user.username, "Pass1234!")

    client.post(
        "/aris3/pos/cash/session/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "cash-open-close"},
        json={
            "transaction_id": "txn-open-close",
            "store_id": str(store.id),
            "action": "OPEN",
            "opening_amount": 60.0,
            "business_date": date.today().isoformat(),
            "timezone": "UTC",
        },
    )

    client.post(
        "/aris3/pos/cash/session/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "cash-in-close"},
        json={
            "transaction_id": "txn-cash-in-close",
            "store_id": str(store.id),
            "action": "CASH_IN",
            "amount": 10.0,
        },
    )

    close_response = client.post(
        "/aris3/pos/cash/session/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "cash-close"},
        json={
            "transaction_id": "txn-close",
            "store_id": str(store.id),
            "action": "CLOSE",
            "counted_cash": 65.0,
        },
    )
    assert close_response.status_code == 200
    assert close_response.json()["expected_cash"] == "70.0"
    assert close_response.json()["counted_cash"] == "65.0"
    assert close_response.json()["difference"] == "-5.0"

    blocked = client.post(
        "/aris3/pos/cash/session/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "cash-in-after-close"},
        json={
            "transaction_id": "txn-cash-in-after",
            "store_id": str(store.id),
            "action": "CASH_IN",
            "amount": 5.0,
        },
    )
    assert blocked.status_code == 422
    assert blocked.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code
