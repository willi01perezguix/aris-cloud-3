from datetime import date

from app.aris3.core.error_catalog import ErrorCatalog
from tests.pos_sales_helpers import create_tenant_user, login, seed_defaults


def test_close_day_uniqueness_and_force_rules(client, db_session):
    seed_defaults(db_session)
    _tenant, store, _other_store, manager = create_tenant_user(
        db_session, suffix="pos-cash-close-uniq", role="MANAGER"
    )
    token = login(client, manager.username, "Pass1234!")
    business_date = date.today()

    open_session = client.post(
        "/aris3/pos/cash/session/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "uniq-open"},
        json={
            "transaction_id": "txn-uniq-open",
            "store_id": str(store.id),
            "action": "OPEN",
            "opening_amount": 50.0,
            "business_date": business_date.isoformat(),
            "timezone": "UTC",
        },
    )
    assert open_session.status_code == 200

    denied_force = client.post(
        "/aris3/pos/cash/day-close/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "uniq-force-denied"},
        json={
            "transaction_id": "txn-uniq-force-denied",
            "store_id": str(store.id),
            "action": "CLOSE_DAY",
            "business_date": business_date.isoformat(),
            "timezone": "UTC",
            "force_if_open_sessions": True,
        },
    )
    assert denied_force.status_code == 422
    assert denied_force.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code

    close_session = client.post(
        "/aris3/pos/cash/session/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "uniq-close-session"},
        json={
            "transaction_id": "txn-uniq-close",
            "store_id": str(store.id),
            "action": "CLOSE",
            "counted_cash": 50.0,
        },
    )
    assert close_session.status_code == 200

    first_close = client.post(
        "/aris3/pos/cash/day-close/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "uniq-day-close"},
        json={
            "transaction_id": "txn-uniq-day-close",
            "store_id": str(store.id),
            "action": "CLOSE_DAY",
            "business_date": business_date.isoformat(),
            "timezone": "UTC",
        },
    )
    assert first_close.status_code == 200

    second_close = client.post(
        "/aris3/pos/cash/day-close/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "uniq-day-close-2"},
        json={
            "transaction_id": "txn-uniq-day-close-2",
            "store_id": str(store.id),
            "action": "CLOSE_DAY",
            "business_date": business_date.isoformat(),
            "timezone": "UTC",
        },
    )
    assert second_close.status_code == 422
    assert second_close.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code
