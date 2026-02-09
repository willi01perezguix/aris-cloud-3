from datetime import date

from app.aris3.core.error_catalog import ErrorCatalog
from tests.pos_sales_helpers import create_tenant_user, login, seed_defaults


def test_pos_cash_cross_tenant_denied(client, db_session):
    seed_defaults(db_session)
    _tenant_a, store_a, _other_store_a, user_a = create_tenant_user(db_session, suffix="pos-cash-sec-a")
    tenant_b, store_b, _other_store_b, _user_b = create_tenant_user(db_session, suffix="pos-cash-sec-b")
    token = login(client, user_a.username, "Pass1234!")

    response = client.post(
        "/aris3/pos/cash/session/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "cash-cross-tenant"},
        json={
            "transaction_id": "txn-cross-tenant",
            "tenant_id": str(tenant_b.id),
            "store_id": str(store_b.id),
            "action": "OPEN",
            "opening_amount": 10.0,
            "business_date": date.today().isoformat(),
            "timezone": "UTC",
        },
    )
    assert response.status_code == 403
    assert response.json()["code"] == ErrorCatalog.CROSS_TENANT_ACCESS_DENIED.code


def test_pos_cash_store_scope_denied(client, db_session):
    seed_defaults(db_session)
    _tenant, store, other_store, user = create_tenant_user(db_session, suffix="pos-cash-scope", role="MANAGER")
    token = login(client, user.username, "Pass1234!")

    response = client.post(
        "/aris3/pos/cash/session/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "cash-store-scope"},
        json={
            "transaction_id": "txn-store-scope",
            "store_id": str(other_store.id),
            "action": "OPEN",
            "opening_amount": 10.0,
            "business_date": date.today().isoformat(),
            "timezone": "UTC",
        },
    )
    assert response.status_code == 403
    assert response.json()["code"] == ErrorCatalog.STORE_SCOPE_MISMATCH.code
