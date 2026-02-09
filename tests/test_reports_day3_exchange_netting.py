import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.aris3.db.models import PosSale
from tests.pos_sales_helpers import (
    create_paid_sale,
    create_stock_item,
    create_tenant_user,
    login,
    open_cash_session,
    sale_line,
    seed_defaults,
)


def test_reports_exchange_netting_no_double_count(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="reports-exchange")
    token = login(client, user.username, "Pass1234!")

    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-EX",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-EX-NEW",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))

    sale = create_paid_sale(
        client,
        token,
        str(store.id),
        [sale_line(line_type="SKU", qty=1, unit_price=20.0, sku="SKU-EX", epc=None, status="PENDING")],
        payments=[{"method": "CASH", "amount": 20.0}],
        create_txn="txn-ex-1",
        checkout_txn="txn-ex-checkout-1",
        idempotency_key="ex-sale-1",
        checkout_idempotency_key="ex-checkout-1",
    )

    original_sale_id = uuid.UUID(sale["header"]["id"])
    db_session.query(PosSale).filter(PosSale.id == original_sale_id).update(
        {"checked_out_at": datetime.utcnow() - timedelta(days=1)}
    )
    db_session.commit()

    exchange_response = client.post(
        f"/aris3/pos/sales/{sale['header']['id']}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "ex-action"},
        json={
            "transaction_id": "txn-exchange",
            "action": "EXCHANGE_ITEMS",
            "receipt_number": "RCPT-EX",
            "return_items": [{"line_id": sale["lines"][0]["id"], "qty": 1, "condition": "NEW"}],
            "exchange_lines": [
                sale_line(line_type="SKU", qty=1, unit_price=30.0, sku="SKU-EX-NEW", epc=None, status="PENDING")
            ],
            "payments": [{"method": "CASH", "amount": 10.0}],
        },
    )
    assert exchange_response.status_code == 200

    today = date.today().isoformat()
    response = client.get(
        "/aris3/reports/overview",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store.id), "from": today, "to": today, "timezone": "UTC"},
    )
    assert response.status_code == 200
    totals = response.json()["totals"]
    assert Decimal(totals["gross_sales"]) == Decimal("30.00")
    assert Decimal(totals["refunds_total"]) == Decimal("20.00")
    assert Decimal(totals["net_sales"]) == Decimal("10.00")
