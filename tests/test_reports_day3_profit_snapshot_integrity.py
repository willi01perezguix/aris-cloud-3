import uuid
from datetime import date
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


def test_reports_profit_uses_sale_line_snapshot(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="reports-profit")
    token = login(client, user.username, "Pass1234!")

    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-PROFIT",
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
        [sale_line(line_type="SKU", qty=1, unit_price=15.0, sku="SKU-PROFIT", epc=None, status="PENDING")],
        payments=[{"method": "CASH", "amount": 15.0}],
        create_txn="txn-profit-1",
        checkout_txn="txn-profit-checkout-1",
        idempotency_key="profit-sale-1",
        checkout_idempotency_key="profit-checkout-1",
    )

    sale_id = uuid.UUID(sale["header"]["id"])
    db_session.query(PosSale).filter(PosSale.id == sale_id).update(
        {"total_due": 999.0, "paid_total": 999.0}
    )
    db_session.commit()

    today = date.today().isoformat()
    response = client.get(
        "/aris3/reports/overview",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store.id), "from": today, "to": today, "timezone": "UTC"},
    )
    assert response.status_code == 200
    totals = response.json()["totals"]
    assert Decimal(totals["gross_sales"]) == Decimal("15.00")
    assert Decimal(totals["net_profit"]) == Decimal("15.00")
