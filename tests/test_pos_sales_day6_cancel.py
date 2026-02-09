from tests.pos_sales_helpers import (
    create_stock_item,
    create_tenant_user,
    login,
    open_cash_session,
    sale_line,
    sale_payload,
    seed_defaults,
)


def test_cancel_draft_success(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="pos-cancel")
    token = login(client, user.username, "Pass1234!")

    payload = sale_payload(
        str(store.id),
        [
            sale_line(
                line_type="SKU",
                qty=1,
                unit_price=5.0,
                sku="SKU-1",
                epc=None,
                status="PENDING",
            )
        ],
        transaction_id="txn-cancel-create",
    )
    create_response = client.post(
        "/aris3/pos/sales",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-cancel-create"},
        json=payload,
    )
    assert create_response.status_code == 201
    sale_id = create_response.json()["header"]["id"]

    cancel_response = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-cancel"},
        json={"transaction_id": "txn-cancel", "action": "cancel"},
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["header"]["status"] == "CANCELED"


def test_cancel_denied_after_checkout(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="pos-cancel-deny")
    token = login(client, user.username, "Pass1234!")
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku=None,
        epc="EPC-99",
        location_code="LOC-1",
        pool="P1",
        status="RFID",
    )
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))

    payload = sale_payload(
        str(store.id),
        [
            sale_line(
                line_type="EPC",
                qty=1,
                unit_price=12.0,
                sku="SKU-99",
                epc="EPC-99",
                status="RFID",
            )
        ],
        transaction_id="txn-cancel-create-2",
    )
    create_response = client.post(
        "/aris3/pos/sales",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-cancel-create-2"},
        json=payload,
    )
    assert create_response.status_code == 201
    sale_id = create_response.json()["header"]["id"]

    checkout_response = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-cancel-checkout"},
        json={
            "transaction_id": "txn-cancel-checkout",
            "action": "checkout",
            "payments": [{"method": "CASH", "amount": 12.0}],
        },
    )
    assert checkout_response.status_code == 200

    cancel_response = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-cancel-denied"},
        json={"transaction_id": "txn-cancel-denied", "action": "cancel"},
    )
    assert cancel_response.status_code == 422
