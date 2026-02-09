from datetime import date

from app.aris3.core.error_catalog import ErrorCatalog
from tests.pos_sales_helpers import create_tenant_user, login, seed_defaults


def test_cash_in_out_success_and_negative_blocked(client, db_session):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix="pos-cash-io")
    token = login(client, user.username, "Pass1234!")
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "cash-open-io"}

    open_response = client.post(
        "/aris3/pos/cash/session/actions",
        headers=headers,
        json={
            "transaction_id": "txn-open-io",
            "store_id": str(store.id),
            "action": "OPEN",
            "opening_amount": 50.0,
            "business_date": date.today().isoformat(),
            "timezone": "UTC",
        },
    )
    assert open_response.status_code == 200

    cash_in = client.post(
        "/aris3/pos/cash/session/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "cash-in-io"},
        json={
            "transaction_id": "txn-cash-in",
            "store_id": str(store.id),
            "action": "CASH_IN",
            "amount": 20.0,
        },
    )
    assert cash_in.status_code == 200
    assert cash_in.json()["expected_cash"] == "70.0"

    cash_out = client.post(
        "/aris3/pos/cash/session/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "cash-out-io"},
        json={
            "transaction_id": "txn-cash-out",
            "store_id": str(store.id),
            "action": "CASH_OUT",
            "amount": 30.0,
        },
    )
    assert cash_out.status_code == 200
    assert cash_out.json()["expected_cash"] == "40.0"

    denied = client.post(
        "/aris3/pos/cash/session/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "cash-out-neg"},
        json={
            "transaction_id": "txn-cash-out-neg",
            "store_id": str(store.id),
            "action": "CASH_OUT",
            "amount": 100.0,
        },
    )
    assert denied.status_code == 422
    assert denied.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code
