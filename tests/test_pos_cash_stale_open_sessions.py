from datetime import date, datetime, timedelta
import uuid

from app.aris3.core.error_catalog import ErrorCatalog
from app.aris3.db.models import PosCashDayClose, PosCashSession
from tests.pos_sales_helpers import create_tenant_user, login, seed_defaults


def _insert_open_session(db_session, *, tenant_id: str, store_id: str, cashier_user_id: str, business_date: date) -> PosCashSession:
    session = PosCashSession(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        store_id=store_id,
        cashier_user_id=cashier_user_id,
        status="OPEN",
        business_date=business_date,
        timezone="UTC",
        opening_amount=100.0,
        expected_cash=100.0,
        opened_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
    )
    db_session.add(session)
    db_session.commit()
    return session


def _insert_closed_day_close(db_session, *, tenant_id: str, store_id: str, cashier_user_id: str, business_date: date) -> None:
    db_session.add(
        PosCashDayClose(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            store_id=store_id,
            business_date=business_date,
            timezone="UTC",
            status="CLOSED",
            force_close=False,
            reason="repair test",
            expected_cash=100.0,
            counted_cash=100.0,
            difference_amount=0.0,
            difference_type="EVEN",
            net_cash_sales=0.0,
            cash_refunds=0.0,
            net_cash_movement=0.0,
            day_close_difference=0.0,
            closed_by_user_id=cashier_user_id,
            closed_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )
    )
    db_session.commit()


def test_current_session_ignores_stale_open_session_from_closed_business_day(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="cash-stale-current")
    token = login(client, user.username, "Pass1234!")
    stale_day = date.today() - timedelta(days=1)
    _insert_open_session(
        db_session,
        tenant_id=str(tenant.id),
        store_id=str(store.id),
        cashier_user_id=str(user.id),
        business_date=stale_day,
    )
    _insert_closed_day_close(
        db_session,
        tenant_id=str(tenant.id),
        store_id=str(store.id),
        cashier_user_id=str(user.id),
        business_date=stale_day,
    )

    current = client.get(
        "/aris3/pos/cash/session/current",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store.id), "cashier_user_id": str(user.id)},
    )
    assert current.status_code == 404
    assert current.json()["code"] == ErrorCatalog.RESOURCE_NOT_FOUND.code


def test_open_new_business_day_not_blocked_by_stale_open_session(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="cash-stale-open")
    token = login(client, user.username, "Pass1234!")
    stale_day = date.today() - timedelta(days=1)
    _insert_open_session(
        db_session,
        tenant_id=str(tenant.id),
        store_id=str(store.id),
        cashier_user_id=str(user.id),
        business_date=stale_day,
    )
    _insert_closed_day_close(
        db_session,
        tenant_id=str(tenant.id),
        store_id=str(store.id),
        cashier_user_id=str(user.id),
        business_date=stale_day,
    )

    open_today = client.post(
        "/aris3/pos/cash/session/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "ik-stale-open-today"},
        json={
            "transaction_id": "txn-stale-open-today",
            "store_id": str(store.id),
            "action": "OPEN",
            "opening_amount": 120.0,
            "business_date": date.today().isoformat(),
            "timezone": "UTC",
        },
    )
    assert open_today.status_code == 200
    assert open_today.json()["status"] == "OPEN"
    assert open_today.json()["business_date"] == date.today().isoformat()


def test_cuts_quote_works_for_valid_current_open_session(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="cash-stale-cut-ok")
    token = login(client, user.username, "Pass1234!")
    current_session = _insert_open_session(
        db_session,
        tenant_id=str(tenant.id),
        store_id=str(store.id),
        cashier_user_id=str(user.id),
        business_date=date.today(),
    )

    quote = client.post(
        "/aris3/pos/cash/cuts/quote",
        headers={"Authorization": f"Bearer {token}"},
        json={"store_id": str(store.id), "cash_session_id": str(current_session.id), "use_last_cut_window": False},
    )
    assert quote.status_code == 200
    assert quote.json()["quote"]["cash_session_id"] == str(current_session.id)


def test_cuts_quote_with_explicit_window_works_for_valid_current_open_session(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="cash-stale-cut-explicit")
    token = login(client, user.username, "Pass1234!")
    current_session = _insert_open_session(
        db_session,
        tenant_id=str(tenant.id),
        store_id=str(store.id),
        cashier_user_id=str(user.id),
        business_date=date.today(),
    )
    from_at = current_session.opened_at + timedelta(minutes=1)
    to_at = from_at + timedelta(minutes=20)

    quote = client.post(
        "/aris3/pos/cash/cuts/quote",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "store_id": str(store.id),
            "cash_session_id": str(current_session.id),
            "use_last_cut_window": False,
            "from_at": from_at.isoformat() + "Z",
            "to_at": to_at.isoformat() + "Z",
            "timezone": "America/Guatemala",
            "cut_type": "PARTIAL",
        },
    )
    assert quote.status_code == 200
    payload = quote.json()["quote"]
    assert payload["cash_session_id"] == str(current_session.id)
    assert payload["from_at"].startswith(from_at.replace(microsecond=0).isoformat())
    assert payload["to_at"].startswith(to_at.replace(microsecond=0).isoformat())


def test_cuts_quote_rejects_invalid_explicit_window(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="cash-stale-cut-window-invalid")
    token = login(client, user.username, "Pass1234!")
    current_session = _insert_open_session(
        db_session,
        tenant_id=str(tenant.id),
        store_id=str(store.id),
        cashier_user_id=str(user.id),
        business_date=date.today(),
    )
    from_at = current_session.opened_at + timedelta(minutes=5)
    to_at = from_at

    quote = client.post(
        "/aris3/pos/cash/cuts/quote",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "store_id": str(store.id),
            "cash_session_id": str(current_session.id),
            "use_last_cut_window": False,
            "from_at": from_at.isoformat() + "Z",
            "to_at": to_at.isoformat() + "Z",
        },
    )
    assert quote.status_code == 422
    assert quote.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code
    assert quote.json()["details"]["message"] == "to_at must be greater than from_at"


def test_cuts_quote_rejects_finalized_day_session_when_directly_referenced(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="cash-stale-cut-reject")
    token = login(client, user.username, "Pass1234!")
    stale_day = date.today() - timedelta(days=1)
    stale_session = _insert_open_session(
        db_session,
        tenant_id=str(tenant.id),
        store_id=str(store.id),
        cashier_user_id=str(user.id),
        business_date=stale_day,
    )
    _insert_closed_day_close(
        db_session,
        tenant_id=str(tenant.id),
        store_id=str(store.id),
        cashier_user_id=str(user.id),
        business_date=stale_day,
    )
    _insert_open_session(
        db_session,
        tenant_id=str(tenant.id),
        store_id=str(store.id),
        cashier_user_id=str(user.id),
        business_date=date.today(),
    )

    quote = client.post(
        "/aris3/pos/cash/cuts/quote",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "store_id": str(store.id),
            "cash_session_id": str(stale_session.id),
            "use_last_cut_window": False,
            "from_at": (datetime.utcnow() - timedelta(minutes=20)).isoformat() + "Z",
            "to_at": datetime.utcnow().isoformat() + "Z",
        },
    )
    assert quote.status_code == 422
    assert quote.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code
    assert "day close already finalized" in quote.json()["details"]["message"]
