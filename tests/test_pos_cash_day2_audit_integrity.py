from datetime import date
from decimal import Decimal

from app.aris3.db.models import AuditEvent
from tests.pos_sales_helpers import create_tenant_user, login, seed_defaults


def test_audit_payloads_for_close_and_day_close(client, db_session):
    seed_defaults(db_session)
    _tenant, store, _other_store, manager = create_tenant_user(
        db_session, suffix="pos-cash-audit", role="MANAGER"
    )
    token = login(client, manager.username, "Pass1234!")
    business_date = date.today()

    open_session = client.post(
        "/aris3/pos/cash/session/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "audit-open"},
        json={
            "transaction_id": "txn-audit-open",
            "store_id": str(store.id),
            "action": "OPEN",
            "opening_amount": 80.0,
            "business_date": business_date.isoformat(),
            "timezone": "UTC",
        },
    )
    assert open_session.status_code == 200

    close_session = client.post(
        "/aris3/pos/cash/session/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "audit-close"},
        json={
            "transaction_id": "txn-audit-close",
            "store_id": str(store.id),
            "action": "CLOSE",
            "counted_cash": 80.0,
            "reason": "Shift close",
        },
    )
    assert close_session.status_code == 200

    day_close = client.post(
        "/aris3/pos/cash/day-close/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "audit-day-close"},
        json={
            "transaction_id": "txn-audit-day-close",
            "store_id": str(store.id),
            "action": "CLOSE_DAY",
            "business_date": business_date.isoformat(),
            "timezone": "UTC",
            "counted_cash": 80.0,
            "reason": "Daily close",
        },
    )
    assert day_close.status_code == 200

    session_audit = (
        db_session.query(AuditEvent).filter(AuditEvent.action == "pos_cash_session.close").first()
    )
    assert session_audit is not None
    assert session_audit.before_payload is not None
    assert session_audit.after_payload is not None
    assert session_audit.event_metadata["transaction_id"] == "txn-audit-close"

    day_close_audit = (
        db_session.query(AuditEvent).filter(AuditEvent.action == "pos_cash_day_close.close").first()
    )
    assert day_close_audit is not None
    assert Decimal(day_close_audit.before_payload["expected_cash"]) == Decimal("80.00")
    assert day_close_audit.after_payload["difference_type"] == "EVEN"
    assert day_close_audit.event_metadata["transaction_id"] == "txn-audit-day-close"
