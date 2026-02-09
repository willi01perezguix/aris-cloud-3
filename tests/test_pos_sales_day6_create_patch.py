from tests.pos_sales_helpers import (
    create_stock_item,
    create_tenant_user,
    login,
    open_cash_session,
    sale_line,
    sale_payload,
    seed_defaults,
)


def test_pos_sale_create_and_patch(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="pos-create")
    token = login(client, user.username, "Pass1234!")

    payload = sale_payload(
        str(store.id),
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
        transaction_id="txn-sale-create",
    )
    response = client.post(
        "/aris3/pos/sales",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-create-1"},
        json=payload,
    )
    assert response.status_code == 201
    sale_id = response.json()["header"]["id"]
    assert response.json()["header"]["status"] == "DRAFT"

    patch_payload = {
        "transaction_id": "txn-sale-patch",
        "lines": [
            sale_line(
                line_type="SKU",
                qty=1,
                unit_price=10.0,
                sku="SKU-2",
                epc=None,
                status="PENDING",
            )
        ],
    }
    patch_response = client.patch(
        f"/aris3/pos/sales/{sale_id}",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-patch-1"},
        json=patch_payload,
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["header"]["status"] == "DRAFT"
    assert len(patch_response.json()["lines"]) == 1


def test_pos_sale_patch_denied_after_checkout(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="pos-patch-deny")
    token = login(client, user.username, "Pass1234!")

    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku=None,
        epc="EPC-1",
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
                unit_price=15.0,
                sku="SKU-1",
                epc="EPC-1",
                status="RFID",
            )
        ],
        transaction_id="txn-sale-create-2",
    )
    create_response = client.post(
        "/aris3/pos/sales",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-create-2"},
        json=payload,
    )
    assert create_response.status_code == 201
    sale_id = create_response.json()["header"]["id"]

    checkout_response = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-checkout-1"},
        json={
            "transaction_id": "txn-checkout-1",
            "action": "checkout",
            "payments": [{"method": "CASH", "amount": 15.0}],
        },
    )
    assert checkout_response.status_code == 200

    patch_payload = {
        "transaction_id": "txn-sale-patch-2",
        "lines": [
            sale_line(
                line_type="SKU",
                qty=1,
                unit_price=10.0,
                sku="SKU-2",
                epc=None,
                status="PENDING",
            )
        ],
    }
    patch_response = client.patch(
        f"/aris3/pos/sales/{sale_id}",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-patch-2"},
        json=patch_payload,
    )
    assert patch_response.status_code == 422
