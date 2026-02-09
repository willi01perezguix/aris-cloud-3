from app.aris3.db.models import StockItem
from tests.pos_sales_helpers import (
    create_paid_sale,
    create_stock_item,
    create_tenant_user,
    login,
    sale_line,
    seed_defaults,
    set_return_policy,
)


def test_non_reusable_epc_assign_new_strategy(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="epc-assign")
    token = login(client, user.username, "Pass1234!")

    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-EPC",
        epc="EPC-1",
        location_code="LOC-1",
        pool="P1",
        status="RFID",
    )

    sale = create_paid_sale(
        client,
        token,
        str(store.id),
        [sale_line(line_type="EPC", qty=1, unit_price=20.0, sku="SKU-EPC", epc="EPC-1", status="NON_REUSABLE_LABEL")],
        payments=[{"method": "CARD", "amount": 20, "authorization_code": "AUTH-EPC"}],
    )
    line_id = sale["lines"][0]["id"]

    set_return_policy(
        client,
        token,
        {
            "allow_refund_card": True,
            "require_receipt": False,
            "non_reusable_label_strategy": "ASSIGN_NEW_EPC",
        },
    )

    response = client.post(
        f"/aris3/pos/sales/{sale['header']['id']}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "refund-epc-assign"},
        json={
            "transaction_id": "txn-epc-1",
            "action": "REFUND_ITEMS",
            "return_items": [{"line_id": line_id, "qty": 1, "condition": "NEW"}],
            "refund_payments": [{"method": "CARD", "amount": 20, "authorization_code": "AUTH-EPC-R"}],
        },
    )
    assert response.status_code == 200

    original_stock = (
        db_session.query(StockItem)
        .filter(StockItem.tenant_id == tenant.id, StockItem.epc == "EPC-1")
        .first()
    )
    assert original_stock is not None
    assert original_stock.status != "RFID"

    replacement_stock = (
        db_session.query(StockItem)
        .filter(StockItem.tenant_id == tenant.id, StockItem.status == "RFID")
        .filter(StockItem.epc.like("NEW-EPC-%"))
        .first()
    )
    assert replacement_stock is not None


def test_non_reusable_epc_to_pending_strategy(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="epc-pending")
    token = login(client, user.username, "Pass1234!")

    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-EPC-2",
        epc="EPC-2",
        location_code="LOC-1",
        pool="P1",
        status="RFID",
    )

    sale = create_paid_sale(
        client,
        token,
        str(store.id),
        [sale_line(line_type="EPC", qty=1, unit_price=22.0, sku="SKU-EPC-2", epc="EPC-2", status="NON_REUSABLE_LABEL")],
        payments=[{"method": "CARD", "amount": 22, "authorization_code": "AUTH-EPC2"}],
    )
    line_id = sale["lines"][0]["id"]

    set_return_policy(
        client,
        token,
        {
            "allow_refund_card": True,
            "require_receipt": False,
            "non_reusable_label_strategy": "TO_PENDING",
        },
    )

    response = client.post(
        f"/aris3/pos/sales/{sale['header']['id']}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "refund-epc-pending"},
        json={
            "transaction_id": "txn-epc-2",
            "action": "REFUND_ITEMS",
            "return_items": [{"line_id": line_id, "qty": 1, "condition": "NEW"}],
            "refund_payments": [{"method": "CARD", "amount": 22, "authorization_code": "AUTH-EPC2-R"}],
        },
    )
    assert response.status_code == 200

    pending_stock = (
        db_session.query(StockItem)
        .filter(StockItem.tenant_id == tenant.id, StockItem.status == "PENDING")
        .first()
    )
    assert pending_stock is not None
    assert pending_stock.epc is None
