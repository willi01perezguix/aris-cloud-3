from datetime import date, timedelta

from app.aris3.core.error_catalog import ErrorCatalog
from tests.pos_sales_helpers import create_tenant_user, login, seed_defaults


def test_day_close_guardrails_and_timezone_business_date(client, db_session):
    seed_defaults(db_session)
    _tenant, store, _other_store, manager = create_tenant_user(
        db_session, suffix="pos-day-close", role="MANAGER"
    )
    manager_token = login(client, manager.username, "Pass1234!")

    business_date = date.today()
    client.post(
        "/aris3/pos/cash/session/actions",
        headers={"Authorization": f"Bearer {manager_token}", "Idempotency-Key": "cash-open-day"},
        json={
            "transaction_id": "txn-open-day",
            "store_id": str(store.id),
            "action": "OPEN",
            "opening_amount": 80.0,
            "business_date": business_date.isoformat(),
            "timezone": "UTC",
        },
    )

    blocked = client.post(
        "/aris3/pos/cash/day-close/actions",
        headers={"Authorization": f"Bearer {manager_token}", "Idempotency-Key": "day-close-blocked"},
        json={
            "transaction_id": "txn-day-close-1",
            "store_id": str(store.id),
            "action": "CLOSE_DAY",
            "business_date": business_date.isoformat(),
            "timezone": "UTC",
        },
    )
    assert blocked.status_code == 422
    assert blocked.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code

    denied_force = client.post(
        "/aris3/pos/cash/day-close/actions",
        headers={"Authorization": f"Bearer {manager_token}", "Idempotency-Key": "day-close-force-denied"},
        json={
            "transaction_id": "txn-day-close-2",
            "store_id": str(store.id),
            "action": "CLOSE_DAY",
            "business_date": business_date.isoformat(),
            "timezone": "UTC",
            "force_if_open_sessions": True,
        },
    )
    assert denied_force.status_code == 422
    assert denied_force.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code

    allowed_force = client.post(
        "/aris3/pos/cash/day-close/actions",
        headers={"Authorization": f"Bearer {manager_token}", "Idempotency-Key": "day-close-force-ok"},
        json={
            "transaction_id": "txn-day-close-3",
            "store_id": str(store.id),
            "action": "CLOSE_DAY",
            "business_date": business_date.isoformat(),
            "timezone": "UTC",
            "force_if_open_sessions": True,
            "reason": "End of day override",
        },
    )
    assert allowed_force.status_code == 200
    assert allowed_force.json()["force_close"] is True

    next_day = business_date + timedelta(days=1)
    allowed_next_day = client.post(
        "/aris3/pos/cash/day-close/actions",
        headers={"Authorization": f"Bearer {manager_token}", "Idempotency-Key": "day-close-next"},
        json={
            "transaction_id": "txn-day-close-4",
            "store_id": str(store.id),
            "action": "CLOSE_DAY",
            "business_date": next_day.isoformat(),
            "timezone": "UTC",
        },
    )
    assert allowed_next_day.status_code == 200
