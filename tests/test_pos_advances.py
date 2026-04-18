from decimal import Decimal

from app.aris3.db.models import DrawerEvent, PosAdvance, PosCashMovement
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


def test_consume_action_after_checkout_consumption_returns_conflict(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="adv-double-consume")
    token = login(client, user.username, "Pass1234!")
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))

    create_stock_item(db_session, tenant_id=str(tenant.id), sku="SKU-ADV", epc=None, location_code="LOC-1", pool="P1", status="PENDING")
    create_stock_item(db_session, tenant_id=str(tenant.id), sku="SKU-ADV", epc=None, location_code="LOC-1", pool="P1", status="PENDING")

    issue_response = client.post(
        "/aris3/pos/advances",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "transaction_id": "txn-adv-issue-double-consume",
            "store_id": str(store.id),
            "customer_name": "Cliente Tres",
            "amount": "8.00",
            "payment_method": "CARD",
        },
    )
    assert issue_response.status_code == 200
    advance = issue_response.json()

    sale_id = _create_sale(client, token, str(store.id), "txn-sale-adv-double-consume")
    checkout_response = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "sale-checkout-adv-double-consume"},
        json={
            "transaction_id": "txn-sale-checkout-adv-double-consume",
            "action": "CHECKOUT",
            "payments": [
                {"method": "ADVANCE", "amount": "8.00", "reference_code": advance["barcode_value"]},
                {"method": "CASH", "amount": "2.00"},
            ],
        },
    )
    assert checkout_response.status_code == 200

    consume_response = client.post(
        f"/aris3/pos/advances/{advance['id']}/actions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "transaction_id": "txn-adv-consume-after-checkout",
            "action": "CONSUME",
            "sale_id": sale_id,
        },
    )
    assert consume_response.status_code == 409
    body = consume_response.json()
    assert body["code"] == "BUSINESS_CONFLICT"
    assert body["details"]["status"] == "CONSUMED"


def test_issue_gift_card_cash_records_liability_and_drawer_event(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="gift-card-cash")
    token = login(client, user.username, "Pass1234!")
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))

    response = client.post(
        "/aris3/pos/advances",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "transaction_id": "txn-gift-card-issue-1",
            "store_id": str(store.id),
            "customer_name": "Gift Customer",
            "amount": "150.00",
            "payment_method": "CASH",
            "voucher_type": "GIFT_CARD",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["voucher_type"] == "GIFT_CARD"
    assert payload["status"] == "ACTIVE"
    assert payload["drawer_open_required"] is True
    assert payload["issued_cash_movement_id"] is not None
    assert payload["drawer_event_instruction"]["already_recorded"] is True
    assert payload["drawer_event_instruction"]["event_type"] == "CASH_IN_DRAWER_OPEN"

    advance = db_session.query(PosAdvance).filter(PosAdvance.id == payload["id"]).one()
    assert advance.voucher_type == "GIFT_CARD"
    movement = db_session.query(PosCashMovement).filter(PosCashMovement.id == payload["issued_cash_movement_id"]).one()
    assert movement.action == "CASH_IN"
    assert Decimal(str(movement.amount)) == Decimal("150.00")
    drawer = db_session.query(DrawerEvent).filter(DrawerEvent.sale_id == advance.id).order_by(DrawerEvent.created_at.desc()).first()
    assert drawer is not None
    assert drawer.event_type == "CASH_IN_DRAWER_OPEN"
    assert payload["drawer_event_instruction"]["drawer_event_id"] == str(drawer.id)


def test_issue_advance_card_creates_non_cash_movement_without_drawer_open(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="adv-card")
    token = login(client, user.username, "Pass1234!")

    response = client.post(
        "/aris3/pos/advances",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "transaction_id": "txn-adv-card-1",
            "store_id": str(store.id),
            "customer_name": "Card Customer",
            "amount": "90.00",
            "payment_method": "CARD",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["voucher_type"] == "ADVANCE"
    assert payload["drawer_open_required"] is False
    assert payload["drawer_event_instruction"] is None
    movement = db_session.query(PosCashMovement).filter(PosCashMovement.id == payload["issued_cash_movement_id"]).one()
    assert movement.action == "ADVANCE_ISSUANCE"
    assert Decimal(str(movement.amount)) == Decimal("90.00")


def test_refund_gift_card_cash_creates_cash_out_and_marks_terminal(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="gift-refund")
    token = login(client, user.username, "Pass1234!")
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))

    issue = client.post(
        "/aris3/pos/advances",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "transaction_id": "txn-gift-refund-issue",
            "store_id": str(store.id),
            "customer_name": "Refundable Gift",
            "amount": "40.00",
            "payment_method": "CASH",
            "voucher_type": "GIFT_CARD",
        },
    )
    assert issue.status_code == 200
    advance_id = issue.json()["id"]

    refund = client.post(
        f"/aris3/pos/advances/{advance_id}/actions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "transaction_id": "txn-gift-refund-1",
            "action": "REFUND",
            "refund_method": "CASH",
        },
    )
    assert refund.status_code == 200
    payload = refund.json()
    assert payload["status"] == "REFUNDED"
    assert payload["refunded_cash_movement_id"] is not None
    movement = db_session.query(PosCashMovement).filter(PosCashMovement.id == payload["refunded_cash_movement_id"]).one()
    assert movement.action == "CASH_OUT"
