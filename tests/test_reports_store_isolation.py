from datetime import date, datetime
from decimal import Decimal

from app.aris3.db.models import PosReturnEvent
from tests.pos_sales_helpers import (
    create_paid_sale,
    create_stock_item,
    create_tenant_user,
    login,
    open_cash_session,
    sale_line,
    seed_defaults,
)


def _seed_paid_sale(client, db_session, token: str, *, tenant_id: str, store_id: str, user_id: str, sku: str, amount: float, suffix: str):
    create_stock_item(
        db_session,
        tenant_id=tenant_id,
        store_id=store_id,
        sku=sku,
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
        sale_price=amount,
    )
    open_cash_session(db_session, tenant_id=tenant_id, store_id=store_id, cashier_user_id=user_id)
    response = create_paid_sale(
        client,
        token,
        store_id,
        [sale_line(line_type="SKU", qty=1, unit_price=amount, sku=sku, epc=None, status="PENDING")],
        payments=[{"method": "CASH", "amount": amount}],
        create_txn=f"txn-iso-create-{suffix}",
        checkout_txn=f"txn-iso-checkout-{suffix}",
        idempotency_key=f"ik-iso-create-{suffix}",
        checkout_idempotency_key=f"ik-iso-checkout-{suffix}",
    )
    return response["header"]["id"]


def _create_refund_event(db_session, *, tenant_id: str, store_id: str, sale_id: str, amount: float):
    db_session.add(
        PosReturnEvent(
            tenant_id=tenant_id,
            store_id=store_id,
            sale_id=sale_id,
            action="REFUND_ITEMS",
            refund_subtotal=amount,
            restocking_fee=0.0,
            refund_total=amount,
            exchange_total=0.0,
            net_adjustment=-amount,
            payload={},
            created_at=datetime.utcnow(),
        )
    )
    db_session.commit()


def test_reports_are_store_isolated_for_overview_daily_calendar_and_exports(client, db_session):
    seed_defaults(db_session)
    tenant, store_a, store_b, user = create_tenant_user(db_session, suffix="reports-store-iso", role="ADMIN")
    token = login(client, user.username, "Pass1234!")

    sale_a = _seed_paid_sale(
        client,
        db_session,
        token,
        tenant_id=str(tenant.id),
        store_id=str(store_a.id),
        user_id=str(user.id),
        sku="SKU-A-ISO",
        amount=100.0,
        suffix="a",
    )
    sale_b = _seed_paid_sale(
        client,
        db_session,
        token,
        tenant_id=str(tenant.id),
        store_id=str(store_b.id),
        user_id=str(user.id),
        sku="SKU-B-ISO",
        amount=40.0,
        suffix="b",
    )
    _create_refund_event(db_session, tenant_id=str(tenant.id), store_id=str(store_a.id), sale_id=sale_a, amount=10.0)
    _create_refund_event(db_session, tenant_id=str(tenant.id), store_id=str(store_b.id), sale_id=sale_b, amount=4.0)

    today = date.today().isoformat()
    overview_a = client.get(
        "/aris3/reports/overview",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store_a.id), "from": today, "to": today, "timezone": "UTC"},
    )
    assert overview_a.status_code == 200
    payload_a = overview_a.json()
    assert Decimal(payload_a["totals"]["gross_sales"]) == Decimal("100.00")
    assert Decimal(payload_a["totals"]["refunds_total"]) == Decimal("10.00")
    assert Decimal(payload_a["totals"]["net_sales"]) == Decimal("90.00")
    assert payload_a["totals"]["orders_paid_count"] == 1
    assert payload_a["meta"]["all_stores"] is False
    assert payload_a["meta"]["resolved_store_id"] == str(store_a.id)
    assert payload_a["meta"]["eligible_sales_count_by_store"][str(store_a.id)] == 1

    overview_b = client.get(
        "/aris3/reports/overview",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store_b.id), "from": today, "to": today, "timezone": "UTC"},
    )
    assert overview_b.status_code == 200
    payload_b = overview_b.json()
    assert Decimal(payload_b["totals"]["gross_sales"]) == Decimal("40.00")
    assert Decimal(payload_b["totals"]["refunds_total"]) == Decimal("4.00")
    assert Decimal(payload_b["totals"]["net_sales"]) == Decimal("36.00")
    assert payload_b["totals"]["orders_paid_count"] == 1
    assert payload_b["meta"]["resolved_store_id"] == str(store_b.id)
    assert payload_b["meta"]["eligible_sales_count_by_store"][str(store_b.id)] == 1

    daily_a = client.get(
        "/aris3/reports/daily",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store_a.id), "from": today, "to": today, "timezone": "UTC"},
    )
    assert daily_a.status_code == 200
    assert Decimal(daily_a.json()["rows"][0]["gross_sales"]) == Decimal("100.00")
    assert Decimal(daily_a.json()["rows"][0]["refunds_total"]) == Decimal("10.00")
    assert Decimal(daily_a.json()["rows"][0]["net_profit"]) == Decimal("90.00")

    calendar_a = client.get(
        "/aris3/reports/calendar",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store_a.id), "from": today, "to": today, "timezone": "UTC"},
    )
    assert calendar_a.status_code == 200
    assert Decimal(calendar_a.json()["rows"][0]["net_sales"]) == Decimal("90.00")
    assert calendar_a.json()["rows"][0]["orders_paid_count"] == 1

    export_response = client.post(
        "/aris3/exports",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "ik-iso-export-a"},
        json={
            "source_type": "reports_overview",
            "format": "csv",
            "filters": {"store_id": str(store_a.id), "from": today, "to": today, "timezone": "UTC"},
            "transaction_id": "txn-iso-export-a",
        },
    )
    assert export_response.status_code == 201
    export_id = export_response.json()["export_id"]
    download = client.get(
        f"/aris3/exports/{export_id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert download.status_code == 200
    content = download.content.decode("utf-8")
    assert "100.00" in content
    assert "90.00" in content
    assert "40.00" not in content


def test_reports_overview_without_store_id_defaults_to_token_store(client, db_session):
    seed_defaults(db_session)
    tenant, store_a, _store_b, manager = create_tenant_user(db_session, suffix="reports-store-default", role="MANAGER")
    token = login(client, manager.username, "Pass1234!")

    _seed_paid_sale(
        client,
        db_session,
        token,
        tenant_id=str(tenant.id),
        store_id=str(store_a.id),
        user_id=str(manager.id),
        sku="SKU-A-DEFAULT",
        amount=55.0,
        suffix="default-a",
    )

    today = date.today().isoformat()
    response = client.get(
        "/aris3/reports/overview",
        headers={"Authorization": f"Bearer {token}"},
        params={"from": today, "to": today, "timezone": "UTC"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["requested_store_id"] is None
    assert payload["meta"]["resolved_store_id"] == str(store_a.id)
    assert Decimal(payload["totals"]["gross_sales"]) == Decimal("55.00")
    assert Decimal(payload["totals"]["refunds_total"]) == Decimal("0.00")
