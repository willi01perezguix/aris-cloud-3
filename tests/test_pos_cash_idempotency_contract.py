from datetime import date

from app.aris3.core.error_catalog import ErrorCatalog
from tests.pos_sales_helpers import create_tenant_user, login, seed_defaults


def test_cash_session_action_requires_idempotency_key(client, db_session):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix="cash-idem-required-session")
    token = login(client, user.username, "Pass1234!")

    payload = {
        "transaction_id": "txn-cash-open-no-idem",
        "store_id": str(store.id),
        "action": "OPEN",
        "opening_amount": 100.0,
        "business_date": date.today().isoformat(),
        "timezone": "UTC",
    }
    response = client.post(
        "/aris3/pos/cash/session/actions",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )

    assert response.status_code == 400
    assert response.json()["code"] == ErrorCatalog.IDEMPOTENCY_KEY_REQUIRED.code


def test_cash_day_close_action_requires_idempotency_key(client, db_session):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix="cash-idem-required-day-close")
    token = login(client, user.username, "Pass1234!")

    payload = {
        "transaction_id": "txn-day-close-no-idem",
        "store_id": str(store.id),
        "action": "CLOSE_DAY",
        "business_date": date.today().isoformat(),
        "timezone": "UTC",
    }
    response = client.post(
        "/aris3/pos/cash/day-close/actions",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )

    assert response.status_code == 400
    assert response.json()["code"] == ErrorCatalog.IDEMPOTENCY_KEY_REQUIRED.code
