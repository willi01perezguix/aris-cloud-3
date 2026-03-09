from tests.pos_sales_helpers import create_stock_item, create_tenant_user, login, sale_line, seed_defaults, open_cash_session


def _ctx(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other, user = create_tenant_user(db_session, suffix="canon-pos-actions")
    token = login(client, user.username, "Pass1234!")
    return str(tenant.id), str(store.id), str(user.id), token


def _create_sale(client, token, store_id, txn, idemp):
    sale = client.post(
        "/aris3/pos/sales",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": idemp},
        json={"transaction_id": txn, "store_id": store_id, "lines": [sale_line(line_type="SKU", qty=1, sku="SKU-CHECKOUT", epc=None)]},
    )
    assert sale.status_code == 201
    return sale.json()["header"]["id"]


def test_pos_sale_actions_canonical_and_cash_business_conflict(client, db_session):
    tenant_id, store_id, user_id, token = _ctx(client, db_session)

    create_stock_item(db_session, tenant_id=tenant_id, sku="SKU-CHECKOUT", epc=None, location_code="LOC-1", pool="P1", status="PENDING", sale_price=25.0)
    sale_id = _create_sale(client, token, store_id, "txn-canonical-checkout-1", "canon-sale-1")

    blocked = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "canon-checkout-blocked"},
        json={"transaction_id": "txn-canonical-checkout-blocked", "action": "CHECKOUT", "payments": [{"method": "CASH", "amount": 25.0}]},
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "BUSINESS_CONFLICT"

    lower = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "canon-checkout-lower"},
        json={"transaction_id": "txn-canonical-checkout-lower", "action": "checkout", "payments": [{"method": "CASH", "amount": 25.0}]},
    )
    assert lower.status_code == 409
    assert lower.json()["code"] == "BUSINESS_CONFLICT"

    open_cash_session(db_session, tenant_id=tenant_id, store_id=store_id, cashier_user_id=user_id)
    create_stock_item(db_session, tenant_id=tenant_id, sku="SKU-CHECKOUT", epc=None, location_code="LOC-1", pool="P1", status="PENDING", sale_price=25.0)
    sale2_id = _create_sale(client, token, store_id, "txn-canonical-checkout-2", "canon-sale-2")

    ok = client.post(
        f"/aris3/pos/sales/{sale2_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "canon-checkout-ok"},
        json={"transaction_id": "txn-canonical-checkout-ok", "action": "CHECKOUT", "payments": [{"method": "CASH", "amount": 25.0}]},
    )
    assert ok.status_code == 200


def test_pos_sale_cancel_action_is_canonical(client, db_session):
    tenant_id, store_id, _user_id, token = _ctx(client, db_session)
    create_stock_item(db_session, tenant_id=tenant_id, sku="SKU-CHECKOUT", epc=None, location_code="LOC-1", pool="P1", status="PENDING", sale_price=25.0)
    sale_id = _create_sale(client, token, store_id, "txn-canonical-cancel-1", "canon-cancel-sale")

    res = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "canon-cancel-action"},
        json={"transaction_id": "txn-canonical-cancel-action", "action": "CANCEL"},
    )
    assert res.status_code == 200
    assert res.json()["header"]["status"] == "CANCELED"
