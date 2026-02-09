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


def test_reports_daily_shape_with_moderate_dataset(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="reports-day5-shape")
    token = login(client, user.username, "Pass1234!")

    for _ in range(3):
        create_stock_item(
            db_session,
            tenant_id=str(tenant.id),
            sku="SKU-1",
            epc=None,
            location_code="LOC-1",
            pool="P1",
            status="PENDING",
        )
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))

    sale_ids = []
    for idx in range(3):
        response = create_paid_sale(
            client,
            token,
            str(store.id),
            [sale_line(line_type="SKU", qty=1, unit_price=10.0, sku="SKU-1", epc=None, status="PENDING")],
            payments=[{"method": "CASH", "amount": 10.0}],
            create_txn=f"txn-shape-sale-{idx}",
            checkout_txn=f"txn-shape-checkout-{idx}",
            idempotency_key=f"shape-sale-{idx}",
            checkout_idempotency_key=f"shape-checkout-{idx}",
        )
        sale_ids.append(response["header"]["id"])

    today = date.today()
    for offset, sale_id in enumerate(sale_ids):
        sale = db_session.get(PosSale, sale_id)
        sale.checked_out_at = datetime.combine(today - timedelta(days=offset), datetime.min.time())
    db_session.commit()

    response = client.get(
        "/aris3/reports/daily",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store.id), "from": (today - timedelta(days=2)).isoformat(), "to": today.isoformat(), "timezone": "UTC"},
    )
    assert response.status_code == 200
    payload = response.json()
    rows = payload["rows"]
    assert len(rows) == 3
    assert payload["totals"]["orders_paid_count"] == 3
    assert Decimal(payload["totals"]["gross_sales"]) == Decimal("30.00")
