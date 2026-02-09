from tests.pos_sales_helpers import (
    create_stock_item,
    create_tenant_user,
    login,
    open_cash_session,
    sale_line,
    sale_payload,
    seed_defaults,
)


def _create_sale(client, token: str, store_id: str, transaction_id: str):
    payload = sale_payload(
        store_id,
        [
            sale_line(
                line_type="SKU",
                qty=2,
                unit_price=5.0,
                sku="SKU-1",
                epc=None,
                status="PENDING",
            )
        ],
        transaction_id=transaction_id,
    )
    response = client.post(
        "/aris3/pos/sales",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": f"pos-sale-{transaction_id}"},
        json=payload,
    )
    assert response.status_code == 201
    return response.json()["header"]["id"]


def test_cash_checkout_success(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="pos-cash")
    token = login(client, user.username, "Pass1234!")
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-1",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-1",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))

    sale_id = _create_sale(client, token, str(store.id), "txn-cash")
    response = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-cash"},
        json={
            "transaction_id": "txn-cash-checkout",
            "action": "checkout",
            "payments": [{"method": "CASH", "amount": 10.0}],
        },
    )
    assert response.status_code == 200
    assert response.json()["header"]["status"] == "PAID"


def test_card_checkout_requires_authorization(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="pos-card")
    token = login(client, user.username, "Pass1234!")
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-1",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-1",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )

    sale_id = _create_sale(client, token, str(store.id), "txn-card")
    fail_response = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-card-fail"},
        json={
            "transaction_id": "txn-card-checkout-1",
            "action": "checkout",
            "payments": [{"method": "CARD", "amount": 10.0}],
        },
    )
    assert fail_response.status_code == 422

    ok_response = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-card-ok"},
        json={
            "transaction_id": "txn-card-checkout-2",
            "action": "checkout",
            "payments": [{"method": "CARD", "amount": 10.0, "authorization_code": "AUTH-1"}],
        },
    )
    assert ok_response.status_code == 200


def test_transfer_checkout_requires_voucher_details(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="pos-transfer")
    token = login(client, user.username, "Pass1234!")
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-1",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-1",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )

    sale_id = _create_sale(client, token, str(store.id), "txn-transfer")
    fail_response = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-transfer-fail"},
        json={
            "transaction_id": "txn-transfer-checkout-1",
            "action": "checkout",
            "payments": [{"method": "TRANSFER", "amount": 10.0}],
        },
    )
    assert fail_response.status_code == 422

    ok_response = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-transfer-ok"},
        json={
            "transaction_id": "txn-transfer-checkout-2",
            "action": "checkout",
            "payments": [
                {
                    "method": "TRANSFER",
                    "amount": 10.0,
                    "bank_name": "Bank",
                    "voucher_number": "V-1",
                }
            ],
        },
    )
    assert ok_response.status_code == 200


def test_mixed_payment_and_change_rules(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="pos-mixed")
    token = login(client, user.username, "Pass1234!")
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-1",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-1",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))

    sale_id = _create_sale(client, token, str(store.id), "txn-mixed")
    ok_response = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-mixed-ok"},
        json={
            "transaction_id": "txn-mixed-checkout",
            "action": "checkout",
            "payments": [
                {"method": "CARD", "amount": 6.0, "authorization_code": "AUTH-2"},
                {"method": "CASH", "amount": 6.0},
            ],
        },
    )
    assert ok_response.status_code == 200
    assert float(ok_response.json()["header"]["change_due"]) == 2.0

    sale_id = _create_sale(client, token, str(store.id), "txn-insufficient")
    fail_response = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-insufficient"},
        json={
            "transaction_id": "txn-insufficient-checkout",
            "action": "checkout",
            "payments": [{"method": "CARD", "amount": 5.0, "authorization_code": "AUTH-3"}],
        },
    )
    assert fail_response.status_code == 422

    sale_id = _create_sale(client, token, str(store.id), "txn-change-only-cash")
    fail_change = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-change-fail"},
        json={
            "transaction_id": "txn-change-fail",
            "action": "checkout",
            "payments": [
                {"method": "CARD", "amount": 12.0, "authorization_code": "AUTH-4"},
            ],
        },
    )
    assert fail_change.status_code == 422
