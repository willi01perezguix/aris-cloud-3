from datetime import date
from decimal import Decimal

from tests.pos_sales_helpers import (
    create_paid_sale,
    create_stock_item,
    create_tenant_user,
    login,
    open_cash_session,
    sale_line,
    seed_defaults,
)


def test_reports_calendar_month_totals_match_daily(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="reports-calendar")
    token = login(client, user.username, "Pass1234!")

    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-CAL",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
    open_cash_session(db_session, tenant_id=str(tenant.id), store_id=str(store.id), cashier_user_id=str(user.id))

    create_paid_sale(
        client,
        token,
        str(store.id),
        [sale_line(line_type="SKU", qty=1, unit_price=12.0, sku="SKU-CAL", epc=None, status="PENDING")],
        payments=[{"method": "CASH", "amount": 12.0}],
        create_txn="txn-cal-1",
        checkout_txn="txn-cal-checkout-1",
        idempotency_key="cal-sale-1",
        checkout_idempotency_key="cal-checkout-1",
    )

    from_date = date.today().isoformat()
    to_date = date.today().isoformat()
    daily_response = client.get(
        "/aris3/reports/daily",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store.id), "from": from_date, "to": to_date, "timezone": "UTC"},
    )
    assert daily_response.status_code == 200
    calendar_response = client.get(
        "/aris3/reports/calendar",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store.id), "from": from_date, "to": to_date, "timezone": "UTC"},
    )
    assert calendar_response.status_code == 200

    daily_totals = daily_response.json()["totals"]
    calendar_totals = calendar_response.json()["totals"]
    assert Decimal(daily_totals["net_sales"]) == Decimal(calendar_totals["net_sales"])
    assert Decimal(daily_totals["net_profit"]) == Decimal(calendar_totals["net_profit"])
    assert daily_totals["orders_paid_count"] == calendar_totals["orders_paid_count"]
    assert len(calendar_response.json()["rows"]) == 1
