from uuid import UUID

from app.aris3.db.models import PosReturnEvent, StockItem
from tests.pos_sales_helpers import (
    create_paid_sale,
    create_stock_item,
    create_tenant_user,
    login,
    sale_line,
    seed_defaults,
    set_return_policy,
)


def test_exchange_atomic_success(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="exchange-atomic")
    token = login(client, user.username, "Pass1234!")

    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-OLD",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-NEW",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )

    sale = create_paid_sale(
        client,
        token,
        str(store.id),
        [sale_line(line_type="SKU", qty=1, unit_price=10.0, sku="SKU-OLD", epc=None, status="PENDING")],
        payments=[{"method": "CARD", "amount": 10, "authorization_code": "AUTH-OLD"}],
    )
    line_id = sale["lines"][0]["id"]

    set_return_policy(
        client,
        token,
        {
            "allow_exchange": True,
            "allow_refund_cash": True,
            "allow_refund_card": True,
            "accepted_conditions": ["NEW"],
            "require_receipt": False,
            "restocking_fee_pct": 0,
        },
    )

    response = client.post(
        f"/aris3/pos/sales/{sale['header']['id']}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "exchange-ok"},
        json={
            "transaction_id": "txn-exchange-1",
            "action": "EXCHANGE_ITEMS",
            "return_items": [{"line_id": line_id, "qty": 1, "condition": "NEW"}],
            "exchange_lines": [
                sale_line(line_type="SKU", qty=1, unit_price=12.0, sku="SKU-NEW", epc=None, status="PENDING")
            ],
            "payments": [{"method": "CARD", "amount": 2, "authorization_code": "AUTH-DELTA"}],
        },
    )
    assert response.status_code == 200

    event = db_session.query(PosReturnEvent).filter(PosReturnEvent.sale_id == UUID(sale["header"]["id"])).first()
    assert event is not None
    assert event.exchange_sale_id is not None

    returned_stock = (
        db_session.query(StockItem)
        .filter(StockItem.tenant_id == tenant.id, StockItem.sku == "SKU-OLD", StockItem.status == "PENDING")
        .first()
    )
    assert returned_stock is not None


def test_exchange_atomic_rollback_on_failure(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="exchange-rollback")
    token = login(client, user.username, "Pass1234!")

    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-ROLL",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )

    sale = create_paid_sale(
        client,
        token,
        str(store.id),
        [sale_line(line_type="SKU", qty=1, unit_price=8.0, sku="SKU-ROLL", epc=None, status="PENDING")],
        payments=[{"method": "CARD", "amount": 8, "authorization_code": "AUTH-ROLL"}],
    )
    line_id = sale["lines"][0]["id"]

    set_return_policy(
        client,
        token,
        {
            "allow_exchange": True,
            "accepted_conditions": ["NEW"],
            "require_receipt": False,
        },
    )

    response = client.post(
        f"/aris3/pos/sales/{sale['header']['id']}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "exchange-fail"},
        json={
            "transaction_id": "txn-exchange-2",
            "action": "EXCHANGE_ITEMS",
            "return_items": [{"line_id": line_id, "qty": 1, "condition": "NEW"}],
            "exchange_lines": [
                sale_line(line_type="SKU", qty=1, unit_price=9.0, sku="SKU-MISSING", epc=None, status="PENDING")
            ],
            "payments": [{"method": "CARD", "amount": 1, "authorization_code": "AUTH-DELTA"}],
        },
    )
    assert response.status_code == 422

    event_count = db_session.query(PosReturnEvent).filter(PosReturnEvent.sale_id == UUID(sale["header"]["id"])).count()
    assert event_count == 0

    sold_stock = (
        db_session.query(StockItem)
        .filter(StockItem.tenant_id == tenant.id, StockItem.sku == "SKU-ROLL", StockItem.status == "SOLD")
        .count()
    )
    assert sold_stock == 1
