from datetime import datetime
import uuid
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


def test_reports_daily_timezone_boundary_and_week_span(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="reports-daily")
    token = login(client, user.username, "Pass1234!")

    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-TZ",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-TZ",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))

    sale_one = create_paid_sale(
        client,
        token,
        str(store.id),
        [sale_line(line_type="SKU", qty=1, unit_price=10.0, sku="SKU-TZ", epc=None, status="PENDING")],
        payments=[{"method": "CASH", "amount": 10.0}],
        create_txn="txn-tz-1",
        checkout_txn="txn-tz-checkout-1",
        idempotency_key="tz-sale-1",
        checkout_idempotency_key="tz-checkout-1",
    )
    sale_two = create_paid_sale(
        client,
        token,
        str(store.id),
        [sale_line(line_type="SKU", qty=1, unit_price=10.0, sku="SKU-TZ", epc=None, status="PENDING")],
        payments=[{"method": "CASH", "amount": 10.0}],
        create_txn="txn-tz-2",
        checkout_txn="txn-tz-checkout-2",
        idempotency_key="tz-sale-2",
        checkout_idempotency_key="tz-checkout-2",
    )

    sale_one_id = sale_one["header"]["id"]
    sale_two_id = sale_two["header"]["id"]
    db_session.query(PosSale).filter(PosSale.id == uuid.UUID(sale_one_id)).update(
        {"checked_out_at": datetime(2024, 5, 1, 3, 30, 0)}
    )
    db_session.query(PosSale).filter(PosSale.id == uuid.UUID(sale_two_id)).update(
        {"checked_out_at": datetime(2024, 5, 1, 5, 0, 0)}
    )
    db_session.commit()

    response = client.get(
        "/aris3/reports/daily",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "store_id": str(store.id),
            "from": "2024-04-29",
            "to": "2024-05-05",
            "timezone": "America/New_York",
        },
    )
    assert response.status_code == 200
    rows = response.json()["rows"]
    assert len(rows) == 7

    row_lookup = {row["business_date"]: row for row in rows}
    assert Decimal(row_lookup["2024-04-30"]["gross_sales"]) == Decimal("10.00")
    assert Decimal(row_lookup["2024-05-01"]["gross_sales"]) == Decimal("10.00")
