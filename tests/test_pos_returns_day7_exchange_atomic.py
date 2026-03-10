from uuid import UUID

from app.aris3.core.error_catalog import ErrorCatalog
from app.aris3.db.models import PosPayment, PosReturnEvent, PosSale, PosSaleLine, StockItem
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

    exchange_sale = db_session.query(PosSale).filter(PosSale.id == event.exchange_sale_id).first()
    assert exchange_sale is not None
    assert exchange_sale.status == "PAID"

    exchange_lines = db_session.query(PosSaleLine).filter(PosSaleLine.sale_id == exchange_sale.id).all()
    assert len(exchange_lines) == 1

    exchange_payments = db_session.query(PosPayment).filter(PosPayment.sale_id == exchange_sale.id).all()
    assert len(exchange_payments) == 1

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


def test_exchange_payment_payload_validation_by_delta_sign(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="exchange-payment-guards")
    token = login(client, user.username, "Pass1234!")

    for sku in ["SKU-DELTA-10", "SKU-DELTA-12", "SKU-DELTA-9", "SKU-DELTA-11"]:
        create_stock_item(
            db_session,
            tenant_id=str(tenant.id),
            sku=sku,
            epc=None,
            location_code="LOC-1",
            pool="P1",
            status="PENDING",
            sale_price=float(sku.split("-")[-1]),
        )

    set_return_policy(
        client,
        token,
        {
            "allow_exchange": True,
            "allow_refund_cash": True,
            "allow_refund_card": True,
            "allow_refund_transfer": True,
            "accepted_conditions": ["NEW"],
            "require_receipt": False,
            "restocking_fee_pct": 0,
        },
    )

    sale_positive = create_paid_sale(
        client,
        token,
        str(store.id),
        [sale_line(line_type="SKU", qty=1, sku="SKU-DELTA-10", epc=None)],
        payments=[{"method": "CARD", "amount": 10, "authorization_code": "AUTH-P"}],
        create_txn="txn-exchange-pos-create",
        checkout_txn="txn-exchange-pos-checkout",
        idempotency_key="exchange-pos-create",
        checkout_idempotency_key="exchange-pos-checkout",
    )
    bad_positive = client.post(
        f"/aris3/pos/sales/{sale_positive['header']['id']}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "exchange-pos-invalid"},
        json={
            "transaction_id": "txn-exchange-pos-invalid",
            "action": "EXCHANGE_ITEMS",
            "return_items": [{"line_id": sale_positive["lines"][0]["id"], "qty": 1, "condition": "NEW"}],
            "exchange_lines": [{"line_type": "SKU", "sku": "SKU-DELTA-12", "qty": 1}],
            "refund_payments": [{"method": "CARD", "amount": 2, "authorization_code": "AUTH-R"}],
        },
    )
    assert bad_positive.status_code == 422
    assert bad_positive.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code

    sale_negative = create_paid_sale(
        client,
        token,
        str(store.id),
        [sale_line(line_type="SKU", qty=1, sku="SKU-DELTA-11", epc=None)],
        payments=[{"method": "CARD", "amount": 11, "authorization_code": "AUTH-N"}],
        create_txn="txn-exchange-neg-create",
        checkout_txn="txn-exchange-neg-checkout",
        idempotency_key="exchange-neg-create",
        checkout_idempotency_key="exchange-neg-checkout",
    )
    bad_negative = client.post(
        f"/aris3/pos/sales/{sale_negative['header']['id']}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "exchange-neg-invalid"},
        json={
            "transaction_id": "txn-exchange-neg-invalid",
            "action": "EXCHANGE_ITEMS",
            "return_items": [{"line_id": sale_negative["lines"][0]["id"], "qty": 1, "condition": "NEW"}],
            "exchange_lines": [{"line_type": "SKU", "sku": "SKU-DELTA-9", "qty": 1}],
            "payments": [{"method": "CARD", "amount": 2, "authorization_code": "AUTH-C"}],
            "refund_payments": [{"method": "CARD", "amount": 2, "authorization_code": "AUTH-RN"}],
        },
    )
    assert bad_negative.status_code == 422
    assert bad_negative.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code

    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-DELTA-10",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
        sale_price=10.0,
    )

    sale_zero = create_paid_sale(
        client,
        token,
        str(store.id),
        [sale_line(line_type="SKU", qty=1, sku="SKU-DELTA-10", epc=None)],
        payments=[{"method": "CARD", "amount": 10, "authorization_code": "AUTH-Z"}],
        create_txn="txn-exchange-zero-create",
        checkout_txn="txn-exchange-zero-checkout",
        idempotency_key="exchange-zero-create",
        checkout_idempotency_key="exchange-zero-checkout",
    )
    bad_zero = client.post(
        f"/aris3/pos/sales/{sale_zero['header']['id']}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "exchange-zero-invalid"},
        json={
            "transaction_id": "txn-exchange-zero-invalid",
            "action": "EXCHANGE_ITEMS",
            "return_items": [{"line_id": sale_zero["lines"][0]["id"], "qty": 1, "condition": "NEW"}],
            "exchange_lines": [{"line_type": "SKU", "sku": "SKU-DELTA-10", "qty": 1}],
            "payments": [{"method": "CARD", "amount": 1, "authorization_code": "AUTH-ZC"}],
        },
    )
    assert bad_zero.status_code == 422
    assert bad_zero.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code
