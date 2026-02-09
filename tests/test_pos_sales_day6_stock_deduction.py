from app.aris3.db.models import StockItem
from tests.pos_sales_helpers import (
    create_stock_item,
    create_tenant_user,
    login,
    open_cash_session,
    sale_line,
    sale_payload,
    seed_defaults,
)


def _create_sale(client, token: str, store_id: str, transaction_id: str, line: dict):
    payload = sale_payload(store_id, [line], transaction_id=transaction_id)
    response = client.post(
        "/aris3/pos/sales",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": f"pos-sale-{transaction_id}"},
        json=payload,
    )
    assert response.status_code == 201
    return response.json()["header"]["id"]


def test_epc_deducts_rfid(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="pos-epc")
    token = login(client, user.username, "Pass1234!")
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-1",
        epc="EPC-10",
        location_code="LOC-1",
        pool="P1",
        status="RFID",
    )
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))

    sale_id = _create_sale(
        client,
        token,
        str(store.id),
        "txn-epc",
        sale_line(
            line_type="EPC",
            qty=1,
            unit_price=8.0,
            sku="SKU-1",
            epc="EPC-10",
            status="RFID",
        ),
    )
    response = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-epc"},
        json={
            "transaction_id": "txn-epc-checkout",
            "action": "checkout",
            "payments": [{"method": "CASH", "amount": 8.0}],
        },
    )
    assert response.status_code == 200

    item = db_session.query(StockItem).filter(StockItem.epc == "EPC-10").first()
    assert item.status == "SOLD"


def test_sku_deducts_pending(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="pos-sku")
    token = login(client, user.username, "Pass1234!")
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-2",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-2",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))

    sale_id = _create_sale(
        client,
        token,
        str(store.id),
        "txn-sku",
        sale_line(
            line_type="SKU",
            qty=2,
            unit_price=4.0,
            sku="SKU-2",
            epc=None,
            status="PENDING",
        ),
    )
    response = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-sku"},
        json={
            "transaction_id": "txn-sku-checkout",
            "action": "checkout",
            "payments": [{"method": "CASH", "amount": 8.0}],
        },
    )
    assert response.status_code == 200

    items = (
        db_session.query(StockItem)
        .filter(StockItem.sku == "SKU-2", StockItem.status == "SOLD")
        .all()
    )
    assert len(items) == 2


def test_no_auto_fallback_between_pools(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="pos-pool")
    token = login(client, user.username, "Pass1234!")
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-3",
        epc=None,
        location_code="LOC-1",
        pool="P2",
        status="PENDING",
    )
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))

    sale_id = _create_sale(
        client,
        token,
        str(store.id),
        "txn-pool",
        sale_line(
            line_type="SKU",
            qty=1,
            unit_price=3.0,
            sku="SKU-3",
            epc=None,
            status="PENDING",
            pool="P1",
        ),
    )
    response = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-pool"},
        json={
            "transaction_id": "txn-pool-checkout",
            "action": "checkout",
            "payments": [{"method": "CASH", "amount": 3.0}],
        },
    )
    assert response.status_code == 422
