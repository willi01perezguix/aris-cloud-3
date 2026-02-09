from datetime import date
from decimal import Decimal

from tests.pos_sales_helpers import (
    create_paid_sale,
    create_stock_item,
    create_tenant_user,
    login,
    open_cash_session,
    sale_line,
    sale_payload,
    seed_defaults,
)


def _report_overview(client, token: str, store_id: str, *, from_date: str, to_date: str):
    return client.get(
        "/aris3/reports/overview",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": store_id, "from": from_date, "to": to_date, "timezone": "UTC"},
    )


def test_reports_overview_paid_only_and_refund_netting(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="reports-overview")
    token = login(client, user.username, "Pass1234!")

    create_stock_item(
        db_session,
        tenant_id=str(tenant.id),
        sku="SKU-1",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
    )
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

    sale_response = create_paid_sale(
        client,
        token,
        str(store.id),
        [sale_line(line_type="SKU", qty=2, unit_price=10.0, sku="SKU-1", epc=None, status="PENDING")],
        payments=[{"method": "CASH", "amount": 20.0}],
        create_txn="txn-overview-sale",
        checkout_txn="txn-overview-checkout",
        idempotency_key="overview-sale",
        checkout_idempotency_key="overview-checkout",
    )

    draft_response = client.post(
        "/aris3/pos/sales",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "overview-draft"},
        json=sale_payload(
            str(store.id),
            [sale_line(line_type="SKU", qty=1, unit_price=5.0, sku="SKU-1", epc=None, status="PENDING")],
            transaction_id="txn-overview-draft",
        ),
    )
    assert draft_response.status_code == 201

    cancel_sale_id = draft_response.json()["header"]["id"]
    cancel_response = client.post(
        f"/aris3/pos/sales/{cancel_sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "overview-cancel"},
        json={"transaction_id": "txn-overview-cancel", "action": "cancel"},
    )
    assert cancel_response.status_code == 200

    return_line_id = sale_response["lines"][0]["id"]
    refund_response = client.post(
        f"/aris3/pos/sales/{sale_response['header']['id']}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "overview-refund"},
        json={
            "transaction_id": "txn-overview-refund",
            "action": "REFUND_ITEMS",
            "receipt_number": "RCPT-1",
            "return_items": [{"line_id": return_line_id, "qty": 1, "condition": "NEW"}],
            "refund_payments": [{"method": "CASH", "amount": 10.0}],
        },
    )
    assert refund_response.status_code == 200

    today = date.today().isoformat()
    response = _report_overview(client, token, str(store.id), from_date=today, to_date=today)
    assert response.status_code == 200
    totals = response.json()["totals"]
    assert Decimal(totals["gross_sales"]) == Decimal("20.00")
    assert Decimal(totals["refunds_total"]) == Decimal("10.00")
    assert Decimal(totals["net_sales"]) == Decimal("10.00")
    assert totals["orders_paid_count"] == 1
    assert Decimal(totals["average_ticket"]) == Decimal("10.00")
