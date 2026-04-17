from app.aris3.db.models import PosAdvance
from tests.pos_sales_helpers import create_stock_item, create_tenant_user, login, open_cash_session, sale_line, sale_payload, seed_defaults


def _create_sale(client, token: str, store_id: str, transaction_id: str):
    response = client.post(
        "/aris3/pos/sales",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": f"sale-{transaction_id}"},
        json=sale_payload(store_id, [sale_line(line_type="SKU", qty=2, unit_price=5.0, sku="SKU-ADV", epc=None)], transaction_id=transaction_id),
    )
    assert response.status_code == 201
    return response.json()["header"]["id"]


def test_issue_advance_and_consume_on_checkout(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="adv-issue")
    token = login(client, user.username, "Pass1234!")

    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))
    create_stock_item(db_session, tenant_id=str(tenant.id), sku="SKU-ADV", epc=None, location_code="LOC-1", pool="P1", status="PENDING")
    create_stock_item(db_session, tenant_id=str(tenant.id), sku="SKU-ADV", epc=None, location_code="LOC-1", pool="P1", status="PENDING")

    issue_response = client.post(
        "/aris3/pos/advances",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "transaction_id": "txn-adv-issue-1",
            "store_id": str(store.id),
            "customer_name": "Cliente Uno",
            "amount": "7.00",
            "payment_method": "CASH",
        },
    )
    assert issue_response.status_code == 200
    advance = issue_response.json()
    assert advance["status"] == "ACTIVE"
    assert advance["barcode_value"].startswith("ADV-")

    sale_id = _create_sale(client, token, str(store.id), "txn-sale-adv-1")
    checkout_response = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "sale-checkout-adv-1"},
        json={
            "transaction_id": "txn-sale-checkout-adv-1",
            "action": "CHECKOUT",
            "payments": [
                {"method": "ADVANCE", "amount": "7.00", "reference_code": advance["barcode_value"]},
                {"method": "CASH", "amount": "3.00"},
            ],
        },
    )
    assert checkout_response.status_code == 200

    row = db_session.query(PosAdvance).filter(PosAdvance.id == advance["id"]).one()
    assert row.status == "CONSUMED"
    assert str(row.consumed_sale_id) == sale_id


def test_advance_cannot_be_reused_after_consumption(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="adv-reuse")
    token = login(client, user.username, "Pass1234!")

    create_stock_item(db_session, tenant_id=str(tenant.id), sku="SKU-ADV", epc=None, location_code="LOC-1", pool="P1", status="PENDING")
    create_stock_item(db_session, tenant_id=str(tenant.id), sku="SKU-ADV", epc=None, location_code="LOC-1", pool="P1", status="PENDING")
    create_stock_item(db_session, tenant_id=str(tenant.id), sku="SKU-ADV", epc=None, location_code="LOC-1", pool="P1", status="PENDING")
    create_stock_item(db_session, tenant_id=str(tenant.id), sku="SKU-ADV", epc=None, location_code="LOC-1", pool="P1", status="PENDING")

    issue_response = client.post(
        "/aris3/pos/advances",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "transaction_id": "txn-adv-issue-2",
            "store_id": str(store.id),
            "customer_name": "Cliente Dos",
            "amount": "5.00",
            "payment_method": "TRANSFER",
        },
    )
    assert issue_response.status_code == 200
    barcode = issue_response.json()["barcode_value"]

    sale_1 = _create_sale(client, token, str(store.id), "txn-sale-adv-2a")
    checkout_1 = client.post(
        f"/aris3/pos/sales/{sale_1}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "sale-checkout-adv-2a"},
        json={
            "transaction_id": "txn-sale-checkout-adv-2a",
            "action": "CHECKOUT",
            "payments": [
                {"method": "ADVANCE", "amount": "5.00", "reference_code": barcode},
                {"method": "TRANSFER", "amount": "5.00", "bank_name": "Bank", "voucher_number": "TRX-1"},
            ],
        },
    )
    assert checkout_1.status_code == 200

    sale_2 = _create_sale(client, token, str(store.id), "txn-sale-adv-2b")
    checkout_2 = client.post(
        f"/aris3/pos/sales/{sale_2}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "sale-checkout-adv-2b"},
        json={
            "transaction_id": "txn-sale-checkout-adv-2b",
            "action": "CHECKOUT",
            "payments": [
                {"method": "ADVANCE", "amount": "5.00", "reference_code": barcode},
                {"method": "TRANSFER", "amount": "5.00", "bank_name": "Bank", "voucher_number": "TRX-2"},
            ],
        },
    )
    assert checkout_2.status_code == 409
