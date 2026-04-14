from app.aris3.core.error_catalog import ErrorCatalog
from tests.pos_sales_helpers import create_tenant_user, login, open_cash_session, seed_defaults
from tests.test_pos_sales_day6_checkout_payments import _create_sale, _seed_two_units


def test_current_session_and_checkout_agree_when_no_open_session(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="cash-current-missing")
    token = login(client, user.username, "Pass1234!")
    _seed_two_units(db_session, str(tenant.id))

    current = client.get(
        "/aris3/pos/cash/session/current",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store.id), "cashier_user_id": str(user.id)},
    )
    assert current.status_code == 404
    assert current.json()["code"] == ErrorCatalog.RESOURCE_NOT_FOUND.code

    sale_id = _create_sale(client, token, str(store.id), "txn-cash-current-missing")
    checkout = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "checkout-cash-current-missing"},
        json={"transaction_id": "txn-cash-current-missing-checkout", "action": "CHECKOUT", "payments": [{"method": "CASH", "amount": 10.0}]},
    )
    assert checkout.status_code == 409
    assert checkout.json()["code"] == ErrorCatalog.BUSINESS_CONFLICT.code


def test_cash_checkout_succeeds_with_valid_open_session(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="cash-current-valid")
    token = login(client, user.username, "Pass1234!")
    _seed_two_units(db_session, str(tenant.id))
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))

    current = client.get(
        "/aris3/pos/cash/session/current",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store.id), "cashier_user_id": str(user.id)},
    )
    assert current.status_code == 200
    assert current.json()["session"]["status"] == "OPEN"

    sale_id = _create_sale(client, token, str(store.id), "txn-cash-current-valid")
    checkout = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "checkout-cash-current-valid"},
        json={"transaction_id": "txn-cash-current-valid-checkout", "action": "CHECKOUT", "payments": [{"method": "CASH", "amount": 10.0}]},
    )
    assert checkout.status_code == 200
    assert checkout.json()["header"]["status"] == "PAID"


def test_current_session_requires_matching_store_cashier_scope(client, db_session):
    seed_defaults(db_session)
    tenant, store, other_store, user = create_tenant_user(db_session, suffix="cash-scope-store")
    token = login(client, user.username, "Pass1234!")
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(other_store.id), cashier_user_id=str(user.id))

    wrong_store = client.get(
        "/aris3/pos/cash/session/current",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store.id), "cashier_user_id": str(user.id)},
    )
    assert wrong_store.status_code == 404


def test_current_session_and_checkout_scope_isolated_per_cashier(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, opener = create_tenant_user(db_session, suffix="cash-scope-cashier-opener")
    token_opener = login(client, opener.username, "Pass1234!")
    _, _, _, cashier = create_tenant_user(db_session, suffix="cash-scope-cashier-target")
    cashier.tenant_id = tenant.id
    cashier.store_id = store.id
    db_session.commit()
    token_cashier = login(client, cashier.username, "Pass1234!")
    _seed_two_units(db_session, str(tenant.id))
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(opener.id))

    current = client.get(
        "/aris3/pos/cash/session/current",
        headers={"Authorization": f"Bearer {token_cashier}"},
        params={"store_id": str(store.id), "cashier_user_id": str(cashier.id)},
    )
    assert current.status_code == 404

    sale_id = _create_sale(client, token_cashier, str(store.id), "txn-cash-scope-cashier")
    checkout = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token_cashier}", "Idempotency-Key": "checkout-cash-scope-cashier"},
        json={"transaction_id": "txn-cash-scope-cashier-checkout", "action": "CHECKOUT", "payments": [{"method": "CASH", "amount": 10.0}]},
    )
    assert checkout.status_code == 200

    current_after = client.get(
        "/aris3/pos/cash/session/current",
        headers={"Authorization": f"Bearer {token_opener}"},
        params={"store_id": str(store.id), "cashier_user_id": str(opener.id)},
    )
    assert current_after.status_code == 200
